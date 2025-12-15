from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Any, Optional
from api import add_device, get_device, remove_device, list_devices, login, logout, is_session_valid, load_objects, open_relay
from devices import Device
from objects import OBJECT_CLASSES
from monitor import start_monitoring, stop_monitoring, fetch_and_save_logs, fetch_and_save_logs
from database import get_new_logs, get_all_logs, save_sent_log, get_unsent_logs
import os
import requests
import time
#dotenv
from dotenv import load_dotenv
load_dotenv()  # Cargar variables de .env

def convert_log_to_agilapps_format(log_dict):
    """Convierte el dict del log al formato esperado por AgilApps."""
    converted = {}
    for key, value in log_dict.items():
        if key == 'time':
            # Convertir timestamp Unix a ISO string
            dt = datetime.fromtimestamp(value)
            converted[key] = dt.isoformat()
        elif isinstance(value, int):
            if value == 0:
                converted[key] = "0.00000"
            else:
                converted[key] = str(value)
        elif isinstance(value, float):
            converted[key] = f"{value:.5f}"
        elif value is None:
            converted[key] = "0.00000"  # Para números None
        else:
            converted[key] = str(value) if value else ""  # Para strings, "" si vacío
    return converted

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

@app.on_event("startup")
async def startup_event():
    """Al iniciar la API, hace login en todos los dispositivos y activa el monitoreo."""
    devices = list_devices()
    for device in devices:
        try:
            if device.session_id is None:
                login(device)
            start_monitoring(device.id)
            print(f"Dispositivo {device.id} ({device.name}) iniciado correctamente.")
        except Exception as e:
            print(f"Error al iniciar dispositivo {device.id} ({device.name}): {e}")

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
        # Hacer un pull inmediato
        await fetch_and_save_logs(device_id)
        return {"message": f"Monitoreo iniciado y pull realizado para dispositivo {device_id}"}
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

@app.post("/send_all_logs")
async def send_all_logs():
    """Envía todos los logs no enviados exitosamente a MONITOR_URL de forma manual."""
    logs = get_unsent_logs()
    if not logs:
        return {"message": "No hay logs no enviados para enviar"}
    
    monitor_url = os.getenv("MONITOR_URL")
    if not monitor_url:
        raise HTTPException(status_code=500, detail="MONITOR_URL no configurada en .env")
    
    data = {
        "ControlIdLogs": {
            "objects": [convert_log_to_agilapps_format(log.__dict__) for log in logs]
        }
    }
    try:
        response = requests.post(monitor_url, json=data, timeout=30)
        response.raise_for_status()
        # Parsear la respuesta y guardar el estado de envío
        resp_data = response.json()
        sent_count = 0
        error_count = 0
        if "Messages" in resp_data:
            for i, msg in enumerate(resp_data["Messages"]):
                if i < len(logs):
                    log = logs[i]
                    log_id = log.id
                    response_id = msg["Id"]
                    status = "success" if response_id == "0" else "error"
                    sent_at = int(time.time())
                    save_sent_log(log_id, sent_at, status, response_id)
                    if status == "success":
                        sent_count += 1
                    else:
                        error_count += 1
        return {"message": f"Enviados {sent_count} logs exitosamente, {error_count} errores a {monitor_url}"}
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error al enviar logs: {e}")

@app.get("/unsent_logs")
async def get_unsent_logs_endpoint():
    """Obtiene los logs que no han sido enviados exitosamente."""
    logs = get_unsent_logs()
    return {"unsent_logs": [log.__dict__ for log in logs]}