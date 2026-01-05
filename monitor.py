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

load_dotenv()  # Cargar variables de .env
MONITOR_URL = os.getenv("MONITOR_URL")

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

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
            if "Ya hay una sesión activa" in str(e):
                logger.info(f"Sesión activa detectada para dispositivo {device_id}, cerrando y reabriendo...")
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
                data = {
                    "ControlIdLogs": {
                        "objects": [convert_log_to_agilapps_format(log.__dict__) for log in new_logs]
                    }
                }
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.post(MONITOR_URL, json=data, timeout=10.0)
                    response.raise_for_status()
                    logger.info(f"Enviados {len(new_logs)} logs iniciales a {MONITOR_URL}")
                    # Parsear la respuesta
                    resp_data = response.json()
                    if "Messages" in resp_data:
                        for i, msg in enumerate(resp_data["Messages"]):
                            if i < len(new_logs):
                                log = new_logs[i]
                                log_id = log.id
                                response_id = msg["Id"]
                                status = "success" if response_id == "0" else "error"
                                sent_at = int(time.time())
                                save_sent_log(log_id, sent_at, status, response_id)
                                logger.info(f"Log inicial {log_id} enviado con status {status}")
                except httpx.RequestError as e:
                    logger.error(f"Error al enviar logs iniciales a {MONITOR_URL}: {e}")
        else:
            logger.info(f"No hay logs iniciales para dispositivo {device_id}")
    except Exception as e:
        logger.error(f"Error al obtener logs iniciales para dispositivo {device_id}: {e}")

async def fetch_and_save_logs(device_id: int):
    """Función que se ejecuta cada minuto para obtener y guardar logs desde el último tiempo guardado."""
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
            if "Ya hay una sesión activa" in str(e):
                logger.info(f"Sesión activa detectada para dispositivo {device_id}, cerrando y reabriendo...")
                await logout(device)
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
                data = {
                    "ControlIdLogs": {
                        "objects": [convert_log_to_agilapps_format(log.__dict__) for log in new_logs]
                    }
                }
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.post(MONITOR_URL, json=data, timeout=10.0)
                    response.raise_for_status()
                    logger.info(f"Enviados {len(new_logs)} logs a {MONITOR_URL}")
                    # Parsear la respuesta y guardar el estado de envío
                    resp_data = response.json()
                    if "Messages" in resp_data:
                        for i, msg in enumerate(resp_data["Messages"]):
                            if i < len(new_logs):
                                log = new_logs[i]
                                log_id = log.id
                                response_id = msg["Id"]
                                status = "success" if response_id == "0" else "error"
                                sent_at = int(time.time())
                                save_sent_log(log_id, sent_at, status, response_id)
                                logger.info(f"Log {log_id} enviado con status {status}")
                except httpx.RequestError as e:
                    logger.error(f"Error al enviar logs a {MONITOR_URL}: {e}")
        else:
            logger.info(f"No hay nuevos logs para dispositivo {device_id}")
    except Exception as e:
        logger.error(f"Error al obtener logs para dispositivo {device_id}: {e}")

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