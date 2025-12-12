import requests
from typing import Optional
from devices import Device
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AuthError(Exception):
    pass


def login(device: Device) -> None:
    """
    Inicia sesión en el dispositivo y guarda la sesión.
    """
    if device.session_id is not None:
        raise AuthError("Ya hay una sesión activa para este dispositivo.")

    url = f"http://{device.ip}/login.fcgi"
    payload = {
        "login": device.login,
        "password": device.password
    }
    headers = {
        "Content-Type": "application/json"
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        device.session_id = data.get("session")
        if not device.session_id:
            raise AuthError("No se recibió session_id en la respuesta de login")
        logger.info(f"Login exitoso para dispositivo {device.ip}")
    except requests.RequestException as e:
        logger.error(f"Error en login para {device.ip}: {e}")
        raise AuthError(f"Error en login: {e}")


def logout(device: Device) -> None:
    """
    Cierra sesión activa.
    """
    if device.session_id is None:
        raise AuthError("No hay sesión activa para este dispositivo.")

    url = f"http://{device.ip}/logout.fcgi?session={device.session_id}"
    try:
        response = requests.post(url, timeout=10)
        response.raise_for_status()
        device.session_id = None
        logger.info(f"Logout exitoso para dispositivo {device.ip}")
    except requests.RequestException as e:
        logger.error(f"Error en logout para {device.ip}: {e}")
        raise AuthError(f"Error en logout: {e}")


def is_session_valid(device: Device) -> bool:
    """
    Verifica si la sesión es válida.
    """
    if device.session_id is None:
        return False
    # Intenta una solicitud simple para verificar
    url = f"http://{device.ip}/load_objects.fcgi?session={device.session_id}"
    payload = {"object": "users", "limit": 1}
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except requests.RequestException:
        return False