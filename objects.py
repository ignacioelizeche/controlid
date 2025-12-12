from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import requests
from devices import Device
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class User:
    id: int
    name: str
    card: Optional[str] = None
    pin: Optional[str] = None


@dataclass
class AccessLog:
    id: int
    user_id: int
    timestamp: str
    event: str


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


def load_objects(device: Device, object_name: str) -> List[Any]:
    """
    Recupera datos del objeto especificado.
    """
    if device.session is None:
        raise ValueError("No hay sesión activa para este dispositivo.")

    if object_name not in OBJECT_CLASSES:
        raise ValueError(f"Objeto '{object_name}' no soportado.")

    url = f"http://{device.ip}/objects/{object_name}"
    headers = {
        "Content-Type": "application/json"
    }
    try:
        response = device.session.post(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list):
            raise ValueError("Respuesta no es una lista.")
        cls = OBJECT_CLASSES[object_name]
        objects = [cls(**item) for item in data]
        logger.info(f"Cargados {len(objects)} objetos '{object_name}' desde {device.ip}")
        return objects
    except requests.RequestException as e:
        logger.error(f"Error al cargar objetos '{object_name}' desde {device.ip}: {e}")
        raise ValueError(f"Error al cargar objetos: {e}")
    except (KeyError, TypeError) as e:
        logger.error(f"Error al parsear datos para '{object_name}' desde {device.ip}: {e}")
        raise ValueError(f"Error al parsear datos: {e}")