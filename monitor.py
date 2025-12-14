from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import logging
import os
import requests
from dotenv import load_dotenv
from api import get_device, login, load_objects, is_session_valid
from database import get_last_log_id, save_logs, init_db
from objects import AccessLog
from datetime import datetime

load_dotenv()  # Cargar variables de .env
MONITOR_URL = os.getenv("MONITOR_URL")

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

def convert_log_to_agilapps_format(log_dict):
    """Convierte el dict del log al formato esperado por AgilApps."""
    converted = {}
    for key, value in log_dict.items():
        if key == 'time':
            # Convertir timestamp Unix a ISO string
            dt = datetime.fromtimestamp(value)
            converted[key] = dt.isoformat()
        elif isinstance(value, (int, float)):
            converted[key] = f"{value:.5f}"
        elif value is None:
            converted[key] = "0.00000"  # Para números None
        else:
            converted[key] = str(value) if value else ""  # Para strings, "" si vacío
    return converted

async def fetch_and_save_logs(device_id: int):
    """Función que se ejecuta cada minuto para obtener y guardar logs."""
    try:
        device = get_device(device_id)
        if not is_session_valid(device):
            login(device)
        # Obtener el último ID guardado
        last_id = get_last_log_id(device_id)
        # Cargar logs desde el último ID +1, pero como la API no soporta offset por ID, cargar todos y filtrar
        # Para eficiencia, cargar con start_time basado en el último time
        # Pero por simplicidad, cargar todos y filtrar nuevos
        logs = load_objects(device, "access_logs")
        new_logs = [log for log in logs if last_id is None or log.id > last_id]
        if new_logs:
            save_logs(new_logs, device_id)
            logger.info(f"Guardados {len(new_logs)} nuevos logs para dispositivo {device_id}")
            # Enviar a la URL externa
            if MONITOR_URL:
                data = {
                    #"device_id": device_id,
                    #"device_name": device.name,
                    "objects": [convert_log_to_agilapps_format(log.__dict__) for log in new_logs]
                }
                try:
                    response = requests.post(MONITOR_URL, json=data, timeout=10)
                    response.raise_for_status()
                    logger.info(f"Enviados {len(new_logs)} logs a {MONITOR_URL}")
                except requests.RequestException as e:
                    logger.error(f"Error al enviar logs a {MONITOR_URL}: {e}")
        else:
            logger.info(f"No hay nuevos logs para dispositivo {device_id}")
    except Exception as e:
        logger.error(f"Error al obtener logs para dispositivo {device_id}: {e}")

def start_monitoring(device_id: int):
    """Inicia el monitoreo para un dispositivo."""
    init_db()
    scheduler.add_job(fetch_and_save_logs, trigger=IntervalTrigger(minutes=1), args=[device_id], id=f"monitor_{device_id}")
    if not scheduler.running:
        scheduler.start()
    logger.info(f"Monitoreo iniciado para dispositivo {device_id}")

def stop_monitoring(device_id: int):
    """Detiene el monitoreo para un dispositivo."""
    scheduler.remove_job(f"monitor_{device_id}")
    logger.info(f"Monitoreo detenido para dispositivo {device_id}")