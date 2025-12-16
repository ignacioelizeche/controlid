import asyncio
import time
import logging
import argparse
import os
from datetime import datetime, timezone
from typing import Optional

import httpx

from api import list_devices, get_device, login, is_session_valid, load_objects
from database import init_db, save_logs, get_last_log_time, save_sent_log
from dotenv import load_dotenv

load_dotenv()  # Cargar variables de .env

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_datetime_to_ts(s: str) -> int:
    """Intentar parsear diferentes formatos de fecha/hora a timestamp UNIX.
    Soporta: 'DD/MM/YYYY HH:MM', 'YYYY-MM-DD HH:MM', ISO, o segundos desde epoch.
    """
    s = s.strip()
    # Si ya es un entero (timestamp)
    if s.isdigit():
        return int(s)
    fmts = ["%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"]
    for fmt in fmts:
        try:
            dt = datetime.strptime(s, fmt)
            return int(dt.timestamp())
        except Exception:
            continue
    # Try ISO parse fallback
    try:
        dt = datetime.fromisoformat(s)
        return int(dt.timestamp())
    except Exception:
        raise ValueError(f"Formato de fecha no soportado: {s}")


async def recover_for_device(device, start_ts: Optional[int] = None, end_ts: Optional[int] = None):
    """Recupera logs desde start_ts (inclusive) hasta end_ts (no usado por load_objects).
    `load_objects` sólo soporta filtro por start_time, así que recuperamos desde start_ts y
    filtramos localmente por `end_ts` si se proporciona.
    """
    logger.info(f"Procesando dispositivo {device.id} - {device.name} ({device.ip})")
    # Asegurar DB inicializada
    init_db()

    # Asegurar sesión
    try:
        if not await is_session_valid(device):
            await login(device)
    except Exception as e:
        logger.error(f"No se pudo autenticar en dispositivo {device.id}: {e}")
        return 0

    # Si no se pasó start_ts, tomar desde último guardado + 1
    if start_ts is None:
        last = get_last_log_time(device.id)
        if last:
            start_ts = last + 1
        else:
            # por defecto, recuperar últimas 7 días
            start_ts = int(time.time()) - (7 * 24 * 3600)

    try:
        objects = await load_objects(device, "access_logs", start_time=start_ts)
    except Exception as e:
        logger.error(f"Error al cargar access_logs desde dispositivo {device.id}: {e}")
        return 0

    # Si se indicó end_ts, filtrar
    if end_ts is not None:
        objects = [o for o in objects if getattr(o, 'time', 0) <= end_ts]

    if not objects:
        logger.info(f"No se encontraron logs nuevos para dispositivo {device.id}")
        return 0

    # Guardar
    try:
        save_logs(objects, device.id)
        logger.info(f"Guardados {len(objects)} logs para dispositivo {device.id}")
        # Enviar a MONITOR_URL si está configurada
        monitor_url = os.getenv("MONITOR_URL")
        if monitor_url:
            # Convertir logs al formato esperado
            def convert_log_to_agilapps_format(log_dict):
                """Convierte un objeto log a formato JSON esperado por AgilApps:
                - `time` -> ISO string
                - los numéricos se envían como números
                - strings nulos -> ""
                - numéricos nulos -> 0
                """
                converted = {}
                for key, value in log_dict.items():
                    if key == 'time':
                        try:
                            dt = datetime.fromtimestamp(int(value), tz=timezone.utc)
                            converted[key] = dt.isoformat()
                        except Exception:
                            try:
                                converted[key] = str(value) if value else ""
                            except Exception:
                                converted[key] = ""
                    else:
                        if isinstance(value, (int, float)):
                            converted[key] = value
                        elif value is None:
                            # Inferir si el campo debería ser numérico por su nombre
                            if any(substr in key for substr in ("id", "value", "confidence", "card", "mask", "type", "component")):
                                converted[key] = 0
                            else:
                                converted[key] = ""
                        else:
                            converted[key] = str(value)
                return converted

            data = {
                "ControlIdLogs": {
                    "objects": [convert_log_to_agilapps_format(log.__dict__) for log in objects]
                }
            }
            # Enviar con reintentos y guardar estado por cada log
            max_retries = 3
            retry_delay = 2
            attempt = 0
            sent_any = False
            while attempt < max_retries:
                attempt += 1
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.post(monitor_url, json=data, timeout=30.0)
                    response.raise_for_status()
                    resp_data = {}
                    try:
                        resp_data = response.json()
                    except Exception:
                        # Si la respuesta no es JSON, marcar todos como enviados
                        resp_data = {}

                    if "Messages" in resp_data and isinstance(resp_data["Messages"], list):
                        for i, msg in enumerate(resp_data["Messages"]):
                            if i < len(objects):
                                log = objects[i]
                                log_id = getattr(log, 'id', None)
                                response_id = msg.get("Id")
                                status = "success" if str(response_id) == "0" else "error"
                                sent_at = int(time.time())
                                if log_id is not None:
                                    save_sent_log(log_id, sent_at, status, response_id)
                                    logger.info(f"Log {log_id} enviado con status {status} (device {device.id})")
                        sent_any = True
                    else:
                        # No Messages -> asumir OK para todos, guardar y loggear cada registro
                        for log in objects:
                            log_id = getattr(log, 'id', None)
                            if log_id is not None:
                                save_sent_log(log_id, int(time.time()), "success", "")
                                logger.info(f"Log {log_id} enviado con status success (device {device.id})")
                        sent_any = True

                    # Si llegamos aquí, romper el ciclo de reintentos
                    break
                except httpx.RequestError as e:
                    logger.warning(f"Intento {attempt}/{max_retries} - error enviando a {monitor_url} para device {device.id}: {e}")
                    if attempt < max_retries:
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2
                    else:
                        logger.error(f"Fallo al enviar logs a {monitor_url} para dispositivo {device.id} después de {max_retries} intentos")
            # Pequeña pausa para evitar saturar el servicio al iterar dispositivos
            await asyncio.sleep(0.5)
        return len(objects)
    except Exception as e:
        logger.error(f"Error al guardar logs para dispositivo {device.id}: {e}")
        return 0


async def main(args):
    # Parsear fechas si las hay
    start_ts = None
    end_ts = None
    if args.from_time:
        start_ts = parse_datetime_to_ts(args.from_time)
    if args.to_time:
        end_ts = parse_datetime_to_ts(args.to_time)

    devices = list_devices()
    total = 0
    for dev in devices:
        try:
            count = await recover_for_device(dev, start_ts=start_ts, end_ts=end_ts)
            total += count
        except Exception as e:
            logger.error(f"Error en dispositivo {dev.id}: {e}")

    logger.info(f"Recuperación completada. Total logs guardados: {total}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Recuperar logs faltantes de todos los dispositivos')
    parser.add_argument('--from', dest='from_time', help="Fecha/hora inicio (ej: '13/12/2025 19:47' o '2025-12-13 19:47' o timestamp)")
    parser.add_argument('--to', dest='to_time', help="Fecha/hora fin (opcional)")
    args = parser.parse_args()
    asyncio.run(main(args))
