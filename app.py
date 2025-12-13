from datetime import datetime, timedelta
import pytz
from fastapi import FastAPI, HTTPException, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Any, Optional
from api import add_device, get_device, remove_device, list_devices, login, logout, is_session_valid, load_objects, open_relay
from devices import Device
from objects import OBJECT_CLASSES
from monitor import start_monitoring, stop_monitoring
from database import get_new_logs

# Asumiendo zona horaria, por ejemplo UTC
tz = pytz.UTC

def format_time(timestamp):
    dt = datetime.fromtimestamp(timestamp, tz)
    return dt.strftime("%H:%M %d/%m/%Y")

def process_logs_for_dashboard(logs):
    devices_data = {}
    announcements = []
    for log in logs:
        device_id = log.device_internal_id
        try:
            device = get_device(device_id)
            device_name = device.name
        except ValueError:
            device_name = f"Dispositivo {device_id}"
        if device_id not in devices_data:
            devices_data[device_id] = {"id": device_id, "name": device_name, "users": {}}
        users = devices_data[device_id]["users"]
        user_id = log.user_id
        if user_id not in users:
            users[user_id] = {"user_id": user_id, "name": None, "entry_time": None, "exit_time": None, "total_hours": 0}
        user = users[user_id]
        if user["entry_time"] is None or log.time < user["entry_time"]:
            user["entry_time"] = log.time
        if user["exit_time"] is None or log.time > user["exit_time"]:
            user["exit_time"] = log.time
        # Asumiendo que event 7 es entrada, 8 salida
        if log.event == 7:
            user["entry_time"] = log.time
        elif log.event == 8:
            user["exit_time"] = log.time
            announcements.append(f"Usuario {user_id} salió a las {format_time(log.time)} del dispositivo {device_name}")
    # Calcular total horas
    for device in devices_data.values():
        for user in device["users"].values():
            if user["entry_time"] and user["exit_time"]:
                total_seconds = user["exit_time"] - user["entry_time"]
                user["total_hours"] = round(total_seconds / 3600, 2)
            user["entry_time"] = format_time(user["entry_time"]) if user["entry_time"] else "N/A"
            user["exit_time"] = format_time(user["exit_time"]) if user["exit_time"] else "N/A"
        device["users"] = list(device["users"].values())
    return list(devices_data.values()), announcements[-10:]  # Últimas 10 anuncios

app = FastAPI(title="Control ID API", description="API para interactuar con dispositivos Control ID", version="1.0.0")
templates = Jinja2Templates(directory="templates")

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

@app.get("/")
async def dashboard(request: Request):
    # Obtener logs de todos los dispositivos
    logs = []
    devices = list_devices()
    for device in devices:
        device_logs = get_new_logs(device.id, None)
        for log in device_logs:
            log.device_internal_id = device.id  # Agregar para identificar
        logs.extend(device_logs)
    # Procesar datos
    devices_data, announcements = process_logs_for_dashboard(logs)
    return templates.TemplateResponse("index.html", {"request": request, "devices_data": devices_data, "announcements": announcements})