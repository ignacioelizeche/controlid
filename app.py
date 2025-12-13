from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Any, Optional
from api import add_device, get_device, remove_device, list_devices, login, logout, is_session_valid, load_objects, open_relay
from devices import Device
from objects import OBJECT_CLASSES
from monitor import start_monitoring, stop_monitoring

app = FastAPI(title="Control ID API", description="API para interactuar con dispositivos Control ID", version="1.0.0")

class DeviceRequest(BaseModel):
    name: str
    ip: str
    login: str
    password: str

class RelayRequest(BaseModel):
    relay_id: int

@app.post("/devices", response_model=dict)
async def create_device(device: DeviceRequest):
    try:
        dev = add_device(device.name, device.ip, device.login, device.password)
        return {"message": f"Dispositivo '{dev.name}' registrado con ID {dev.id}"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/devices", response_model=List[dict])
async def get_devices():
    devices = list_devices()
    return [{"id": d.id, "name": d.name, "ip": d.ip, "device_id": d.device_id, "has_session": d.session_id is not None} for d in devices]

@app.delete("/devices/{device_id}")
async def delete_device(device_id: int):
    try:
        remove_device(device_id)
        return {"message": f"Dispositivo {device_id} eliminado"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/devices/{device_id}/login")
async def device_login(device_id: int):
    try:
        device = get_device(device_id)
        login(device)
        return {"message": f"Login exitoso para dispositivo '{device.name}' (ID {device_id})"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@app.post("/devices/{device_id}/logout")
async def device_logout(device_id: int):
    try:
        device = get_device(device_id)
        logout(device)
        return {"message": f"Logout exitoso para dispositivo '{device.name}' (ID {device_id})"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/devices/{device_id}/session")
async def check_session(device_id: int):
    try:
        device = get_device(device_id)
        valid = is_session_valid(device)
        return {"valid": valid}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/devices/{device_id}/objects/{object_name}")
async def get_objects(device_id: int, object_name: str, start_time: Optional[int] = None):
    if object_name not in OBJECT_CLASSES:
        raise HTTPException(status_code=400, detail=f"Objeto '{object_name}' no soportado")
    try:
        device = get_device(device_id)
        objects = load_objects(device, object_name, start_time)
        return {"objects": [obj.__dict__ for obj in objects]}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/devices/{device_id}/control/relay")
async def control_relay(device_id: int, relay: RelayRequest):
    try:
        device = get_device(device_id)
        open_relay(device, relay.relay_id)
        return {"message": f"Relé {relay.relay_id} liberado en dispositivo '{device.name}' (ID {device_id})"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/devices/{device_id}/monitor/start")
async def start_device_monitoring(device_id: int):
    try:
        start_monitoring(device_id)
        return {"message": f"Monitoreo iniciado para dispositivo {device_id}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/devices/{device_id}/monitor/stop")
async def stop_device_monitoring(device_id: int):
    try:
        stop_monitoring(device_id)
        return {"message": f"Monitoreo detenido para dispositivo {device_id}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))