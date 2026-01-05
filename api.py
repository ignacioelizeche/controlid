from devices import device_manager, Device
from auth import login, logout, is_session_valid
from objects import load_objects
from controls import open_relay
from typing import List, Any


def get_device(device_id: int) -> Device:
    """
    Obtiene un dispositivo por ID interno.
    """
    return device_manager.get_device(device_id)


def add_device(name: str, ip: str, login: str, password: str) -> Device:
    """
    Registra un nuevo dispositivo.
    """
    return device_manager.add_device(name, ip, login, password)


def remove_device(device_id: int) -> None:
    """
    Elimina un dispositivo por ID.
    """
    device_manager.remove_device(device_id)


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