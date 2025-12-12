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
    if device.session is not None:
        raise AuthError("Ya hay una sesión activa para este dispositivo.")

    session = requests.Session()
    url = f"http://{device.ip}/login"
    payload = {
        "login": device.login,
        "password": device.password
    }
    headers = {
        "Content-Type": "application/json"
    }
    try:
        response = session.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        # Asumiendo que el login exitoso establece cookies o algo
        device.session = session
        logger.info(f"Login exitoso para dispositivo {device.ip}")
    except requests.RequestException as e:
        logger.error(f"Error en login para {device.ip}: {e}")
        raise AuthError(f"Error en login: {e}")


def logout(device: Device) -> None:
    """
    Cierra sesión activa.
    """
    if device.session is None:
        raise AuthError("No hay sesión activa para este dispositivo.")

    url = f"http://{device.ip}/logout"
    try:
        response = device.session.post(url, timeout=10)
        response.raise_for_status()
        device.session.close()
        device.session = None
        logger.info(f"Logout exitoso para dispositivo {device.ip}")
    except requests.RequestException as e:
        logger.error(f"Error en logout para {device.ip}: {e}")
        raise AuthError(f"Error en logout: {e}")


def is_session_valid(device: Device) -> bool:
    """
    Verifica si la sesión es válida.
    """
    if device.session is None:
        return False
    # Intenta una solicitud simple para verificar
    url = f"http://{device.ip}/status"  # Asumiendo un endpoint de status
    try:
        response = device.session.get(url, timeout=10)
        return response.status_code == 200
    except requests.RequestException:
        return False