from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Any
from api import add_device, get_device, remove_device, list_devices, login, logout, is_session_valid, load_objects, open_relay
from devices import Device
from objects import OBJECT_CLASSES

app = FastAPI(title="Control ID API", description="API para interactuar con dispositivos Control ID", version="1.0.0")

class DeviceRequest(BaseModel):
    ip: str
    login: str
    password: str

class RelayRequest(BaseModel):
    relay_id: int

@app.post("/devices", response_model=dict)
async def create_device(device: DeviceRequest):
    try:
        dev = add_device(device.ip, device.login, device.password)
        return {"message": f"Dispositivo {dev.ip} registrado"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/devices", response_model=List[dict])
async def get_devices():
    devices = list_devices()
    return [{"ip": d.ip, "login": d.login, "has_session": d.session is not None} for d in devices]

@app.delete("/devices/{ip}")
async def delete_device(ip: str):
    try:
        remove_device(ip)
        return {"message": f"Dispositivo {ip} eliminado"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/devices/{ip}/login")
async def device_login(ip: str):
    try:
        device = get_device(ip)
        login(device)
        return {"message": f"Login exitoso para {ip}"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@app.post("/devices/{ip}/logout")
async def device_logout(ip: str):
    try:
        device = get_device(ip)
        logout(device)
        return {"message": f"Logout exitoso para {ip}"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/devices/{ip}/session")
async def check_session(ip: str):
    try:
        device = get_device(ip)
        valid = is_session_valid(device)
        return {"valid": valid}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/devices/{ip}/objects/{object_name}")
async def get_objects(ip: str, object_name: str):
    if object_name not in OBJECT_CLASSES:
        raise HTTPException(status_code=400, detail=f"Objeto '{object_name}' no soportado")
    try:
        device = get_device(ip)
        objects = load_objects(device, object_name)
        return {"objects": [obj.__dict__ for obj in objects]}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/devices/{ip}/control/relay")
async def control_relay(ip: str, relay: RelayRequest):
    try:
        device = get_device(ip)
        open_relay(device, relay.relay_id)
        return {"message": f"Relé {relay.relay_id} liberado en {ip}"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))