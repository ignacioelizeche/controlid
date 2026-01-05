import httpx
from devices import Device
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def open_relay(device: Device, relay_id: int) -> None:
    """
    Libera un relé (async).
    """
    if device.session_id is None:
        raise ValueError("No hay sesión activa para este dispositivo.")

    url = f"http://{device.ip}/control/relay.fcgi?session={device.session_id}"
    payload = {
        "action": "open",
        "relay_id": relay_id
    }
    headers = {
        "Content-Type": "application/json"
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers, timeout=10.0)
        response.raise_for_status()
        logger.info(f"Relé {relay_id} liberado en dispositivo {device.ip}")
    except httpx.RequestError as e:
        logger.error(f"Error al liberar relé {relay_id} en {device.ip}: {e}")
        raise ValueError(f"Error al liberar relé: {e}")


# Agregar más funciones de control aquí, como crear usuario, etc.