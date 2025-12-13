from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Any, Optional
from api import add_device, get_device, remove_device, list_devices, login, logout, is_session_valid, load_objects, open_relay
from devices import Device
from objects import OBJECT_CLASSES
from monitor import start_monitoring, stop_monitoring
from database import get_new_logs

def format_time(timestamp):
    dt = datetime.fromtimestamp(timestamp)  # Asume que el timestamp ya está en hora local
    return dt.strftime("%H:%M %d/%m/%Y")

def process_logs_for_dashboard(logs):
    devices_data = {}
    announcements = []
    # Agrupar logs por dispositivo y usuario
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
            users[user_id] = {"user_id": user_id, "name": None, "logs": []}
        users[user_id]["logs"].append(log)
    
    # Procesar logs por usuario para crear sesiones
    for device in devices_data.values():
        for user in device["users"].values():
            user_logs = sorted(user["logs"], key=lambda l: l.time)  # Ordenar por tiempo
            sessions = []
            i = 0
            while i < len(user_logs):
                entry_ts = user_logs[i].time
                if i + 1 < len(user_logs):
                    exit_ts = user_logs[i + 1].time
                    total_seconds = exit_ts - entry_ts
                    total_hours = round(total_seconds / 3600, 2)
                    sessions.append({
                        "entry_ts": entry_ts,
                        "exit_ts": exit_ts,
                        "entry_time": format_time(entry_ts),
                        "exit_time": format_time(exit_ts),
                        "total_hours": total_hours
                    })
                    announcements.append(f"Usuario {user['user_id']} salió a las {format_time(exit_ts)} del dispositivo {device['name']}")
                    i += 2
                else:
                    sessions.append({
                        "entry_ts": entry_ts,
                        "exit_ts": None,
                        "entry_time": format_time(entry_ts),
                        "exit_time": "En progreso",
                        "total_hours": "N/A"
                    })
                    i += 1
            # Fusionar sesiones si el gap entre salida y siguiente entrada es < 1 minuto
            merged_sessions = []
            for session in sessions:
                if session["exit_ts"] is None:
                    merged_sessions.append(session)
                    continue
                if not merged_sessions or (session["entry_ts"] - merged_sessions[-1]["exit_ts"]) >= 60:
                    merged_sessions.append(session)
                else:
                    # Fusionar: actualizar la salida de la sesión anterior
                    merged_sessions[-1]["exit_ts"] = session["exit_ts"]
                    merged_sessions[-1]["exit_time"] = format_time(session["exit_ts"])
                    merged_sessions[-1]["total_hours"] = round((session["exit_ts"] - merged_sessions[-1]["entry_ts"]) / 3600, 2)
            user["sessions"] = merged_sessions
            del user["logs"]  # Limpiar logs
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