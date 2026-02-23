from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import logging
import os
import httpx
from dotenv import load_dotenv
from api import get_device, login, logout, load_objects, is_session_valid
from database import save_logs, init_db, save_sent_log, get_last_log_time
from objects import AccessLog
import time
from datetime import datetime, timezone
import asyncio

load_dotenv()  # Cargar variables de .env
MONITOR_URL = os.getenv("MONITOR_URL")

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

# Configuración de reintentos
MAX_RETRIES = 3
RETRY_DELAY = 5  # segundos

def convert_log_to_agilapps_format(log_dict):
    """Convierte el dict del log al formato esperado por AgilApps."""
    converted = {}
    for key, value in log_dict.items():
        if key == 'time':
            # Convertir timestamp Unix a ISO string (interpretado como UTC)
            try:
                dt = datetime.fromtimestamp(int(value), tz=timezone.utc)
                converted[key] = dt.isoformat()
            except Exception:
                converted[key] = ""
        elif isinstance(value, int):
            converted[key] = value
        elif isinstance(value, float):
            converted[key] = value
        elif value is None:
            converted[key] = None
        else:
            converted[key] = str(value) if value else ""  # Para strings, "" si vacío
    return converted

async def fetch_initial_logs(device_id: int):
    """Función que se ejecuta al iniciar el monitoreo para obtener logs desde el último tiempo guardado."""
    retry_count = 0
    while retry_count < MAX_RETRIES:
        try:
            device = get_device(device_id)
            if not await is_session_valid(device):
                await login(device)
            # Obtener el último tiempo guardado
            last_time = get_last_log_time(device_id)
            # Cargar logs desde el último tiempo +1
            start_time = last_time + 1 if last_time else None
            try:
                logs = await load_objects(device, "access_logs", start_time=start_time)
            except Exception as e:
                if "Ya hay una sesión activa" in str(e) or "Sesión inválida" in str(e):
                    logger.info(f"Sesión inválida detectada para dispositivo {device_id}, cerrando y reabriendo...")
                    await logout(device)
                    await login(device)
                    logs = await load_objects(device, "access_logs", start_time=start_time)
                else:
                    raise
            new_logs = logs  # Asumiendo que load_objects ya filtra por start_time
            if new_logs:
                save_logs(new_logs, device_id)
                logger.info(f"Guardados {len(new_logs)} logs iniciales para dispositivo {device_id}")
                # Enviar a la URL externa si hay MONITOR_URL
                if MONITOR_URL:
                    await send_logs_to_monitor(new_logs, device_id)
            else:
                logger.info(f"No hay logs iniciales para dispositivo {device_id}")
            return  # Éxito, salir

        except Exception as e:
            retry_count += 1
            logger.warning(f"Intento {retry_count}/{MAX_RETRIES} falló para logs iniciales del dispositivo {device_id}: {e}")
            if retry_count < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)
            else:
                logger.error(f"Error crítico al obtener logs iniciales para dispositivo {device_id} después de {MAX_RETRIES} intentos: {e}")

async def fetch_and_save_logs(device_id: int):
    """Función que se ejecuta cada minuto para obtener y guardar logs desde el último tiempo guardado."""
    retry_count = 0
    while retry_count < MAX_RETRIES:
        try:
            device = get_device(device_id)

            # Verificar y reconectar a la sesión con reintentos
            if not await is_session_valid(device):
                logger.info(f"Sesión inválida para dispositivo {device_id}, reconectando...")
                try:
                    await logout(device)
                except:
                    pass
                await login(device)

            # Obtener el último tiempo guardado
            last_time = get_last_log_time(device_id)
            # Cargar logs desde el último tiempo +1
            start_time = last_time + 1 if last_time else None

            try:
                logs = await load_objects(device, "access_logs", start_time=start_time)
            except Exception as e:
                error_msg = str(e)
                if "Ya hay una sesión activa" in error_msg or "Sesión inválida" in error_msg:
                    logger.warning(f"Sesión detectada como inválida para dispositivo {device_id}, reconectando...")
                    await logout(device)
                    await asyncio.sleep(1)
                    await login(device)
                    logs = await load_objects(device, "access_logs", start_time=start_time)
                else:
                    raise

            new_logs = logs  # Asumiendo que load_objects filtra por start_time
            if new_logs:
                save_logs(new_logs, device_id)
                logger.info(f"Guardados {len(new_logs)} nuevos logs para dispositivo {device_id}")
                # Enviar a la URL externa
                if MONITOR_URL:
                    await send_logs_to_monitor(new_logs, device_id)
            else:
                logger.debug(f"No hay nuevos logs para dispositivo {device_id}")

            return  # Éxito, salir

        except Exception as e:
            retry_count += 1
            logger.warning(f"Intento {retry_count}/{MAX_RETRIES} falló para dispositivo {device_id}: {e}")
            if retry_count < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)
            else:
                logger.error(f"Error crítico al obtener logs para dispositivo {device_id} después de {MAX_RETRIES} intentos: {e}")

async def send_logs_to_monitor(logs, device_id: int):
    """Envía logs a la URL del monitor con reintentos."""
    data = {
        "ControlIdLogs": {
            "objects": [convert_log_to_agilapps_format(log.__dict__) for log in logs]
        }
    }

    retry_count = 0
    while retry_count < MAX_RETRIES:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(MONITOR_URL, json=data, timeout=30.0)
            response.raise_for_status()
            logger.info(f"Enviados {len(logs)} logs a {MONITOR_URL}")

            # Parsear la respuesta y guardar el estado de envío
            resp_data = response.json()
            logger.debug(f"Respuesta del servidor para device {device_id}: {resp_data}")
            if "Messages" in resp_data:
                for i, msg in enumerate(resp_data["Messages"]):
                    if i < len(logs):
                        log = logs[i]
                        log_id = log.id
                        response_id = msg["Id"]
                        status = "success" if response_id == "0" else "error"
                        sent_at = int(time.time())
                        save_sent_log(log_id, sent_at, status, response_id)
                        logger.debug(f"Log {log_id} enviado con status {status}")
            return  # Éxito, salir

        except httpx.RequestError as e:
            retry_count += 1
            logger.warning(f"Intento de envío {retry_count}/{MAX_RETRIES} falló para device {device_id}: {e}")
            if retry_count < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)
            else:
                logger.error(f"Error crítico al enviar logs para device {device_id} después de {MAX_RETRIES} intentos: {e}")

def start_monitoring(device_id: int):
    """Inicia el monitoreo para un dispositivo."""
    init_db()
    # Fetch inicial de logs desde el último tiempo guardado
    import asyncio
    asyncio.create_task(fetch_initial_logs(device_id))
    scheduler.add_job(fetch_and_save_logs, trigger=IntervalTrigger(minutes=1), args=[device_id], id=f"monitor_{device_id}")
    if not scheduler.running:
        scheduler.start()
    logger.info(f"Monitoreo iniciado para dispositivo {device_id}")

def stop_monitoring(device_id: int):
    """Detiene el monitoreo para un dispositivo."""
    try:
        scheduler.remove_job(f"monitor_{device_id}")
        logger.info(f"Monitoreo detenido para dispositivo {device_id}")
    except Exception:
        logger.warning(f"No se encontró job de monitoreo para device {device_id}")