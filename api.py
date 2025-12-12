from devices import device_manager, Device
from auth import login, logout, is_session_valid
from objects import load_objects
from controls import open_relay
from typing import List, Any


def get_device(ip: str) -> Device:
    """
    Obtiene un dispositivo por IP.
    """
    return device_manager.get_device(ip)


def add_device(ip: str, login: str, password: str) -> Device:
    """
    Registra un nuevo dispositivo.
    """
    return device_manager.add_device(ip, login, password)


def remove_device(ip: str) -> None:
    """
    Elimina un dispositivo.
    """
    device_manager.remove_device(ip)


def list_devices() -> List[Device]:
    """
    Lista todos los dispositivos registrados.
    """
    return device_manager.list_devices()


# Re-exportar funciones de auth y objects para conveniencia
__all__ = [
    "get_device", "add_device", "remove_device", "list_devices",
    "login", "logout", "is_session_valid",
    "load_objects", "open_relay"
]