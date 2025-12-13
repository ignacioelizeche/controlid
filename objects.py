from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import requests
from devices import Device
import logging
import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class User:
    id: int
    name: str
    registration: Optional[str] = None
    password: Optional[str] = None
    salt: Optional[str] = None
    expires: Optional[int] = None
    user_type_id: Optional[int] = None
    begin_time: Optional[int] = None
    end_time: Optional[int] = None
    image_timestamp: Optional[int] = None
    last_access: Optional[int] = None
    panic_password: Optional[str] = None
    panic_salt: Optional[str] = None
    card: Optional[str] = None
    pin: Optional[str] = None


@dataclass
class AccessLog:
    id: int
    time: int
    event: int
    device_id: Optional[int] = None
    identifier_id: Optional[int] = None
    user_id: Optional[int] = None
    portal_id: Optional[int] = None
    identification_rule_id: Optional[int] = None
    qrcode_value: Optional[str] = None
    pin_value: Optional[str] = None
    card_value: Optional[int] = None
    confidence: Optional[int] = None
    mask: Optional[int] = None
    log_type_id: Optional[int] = None
    component_id: Optional[int] = None


@dataclass
class Card:
    id: int
    user_id: int
    card_number: str


@dataclass
class QRCode:
    id: int
    user_id: int
    code: str


@dataclass
class UHFTag:
    id: int
    user_id: int
    tag: str


@dataclass
class PIN:
    id: int
    user_id: int
    pin: str


@dataclass
class AlarmLog:
    id: int
    timestamp: str
    alarm_type: str
    description: str


# Mapa de nombres a clases
OBJECT_CLASSES = {
    "users": User,
    "access_logs": AccessLog,
    "cards": Card,
    "qrcodes": QRCode,
    "uhf_tags": UHFTag,
    "pins": PIN,
    "alarm_logs": AlarmLog,
}


def load_objects(device: Device, object_name: str, start_time: Optional[int] = None) -> List[Any]:
    """
    Recupera datos del objeto especificado.
    start_time: Para access_logs, filtra por time >= start_time (Unix timestamp). Si no se especifica, filtra desde el inicio del día actual.
    """
    if device.session_id is None:
        raise ValueError("No hay sesión activa para este dispositivo.")

    if object_name not in OBJECT_CLASSES:
        raise ValueError(f"Objeto '{object_name}' no soportado.")

    url = f"http://{device.ip}/load_objects.fcgi?session={device.session_id}"
    payload = {
        "object": object_name
    }
    if object_name == "access_logs":
        if start_time is None:
            # Filtrar desde el inicio del día actual
            today_start = datetime.datetime.combine(datetime.date.today(), datetime.time.min)
            start_time = int(today_start.timestamp())
        payload["where"] = {
            "access_logs": {
                "time": {">=": start_time}
            }
        }
    headers = {
        "Content-Type": "application/json"
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        if object_name not in data:
            raise ValueError("Respuesta no contiene los objetos esperados.")
        objects_data = data[object_name]
        if not isinstance(objects_data, list):
            raise ValueError("Respuesta no es una lista.")
        cls = OBJECT_CLASSES[object_name]
        objects = [cls(**item) for item in objects_data]
        logger.info(f"Cargados {len(objects)} objetos '{object_name}' desde {device.ip}")
        return objects
    except requests.RequestException as e:
        logger.error(f"Error al cargar objetos '{object_name}' desde {device.ip}: {e}")
        raise ValueError(f"Error al cargar objetos: {e}")
    except (KeyError, TypeError) as e:
        logger.error(f"Error al parsear datos para '{object_name}' desde {device.ip}: {e}")
        raise ValueError(f"Error al parsear datos: {e}")