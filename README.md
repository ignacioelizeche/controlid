# Control ID API

API modular en Python para interactuar con dispositivos de Control ID usando REST/HTTP POST con JSON.

## Instalación

### Windows
1. Crea un entorno virtual:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

2. Instala dependencias:
   ```bash
   pip install -r requirements.txt
   ```

### Linux/Mac
1. Crea un entorno virtual:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Instala dependencias:
   ```bash
   pip install -r requirements.txt
   ```

## Uso como Librería

```python
from api import add_device, get_device, login, load_objects, logout, open_relay

# Registrar dispositivo
device = add_device("Dispositivo Principal", "192.168.100.22", "admin", "password")
print(f"Dispositivo registrado con ID {device.id}")

# Obtener dispositivo por ID
device = get_device(1)

# Login
login(device)

# Cargar objetos
logs = load_objects(device, "access_logs")  # Por defecto, solo logs de hoy
users = load_objects(device, "users")

# Cargar access_logs desde una hora específica (ejemplo: desde el 1 de enero 2025)
import time
start_timestamp = int(time.mktime(time.strptime("2025-01-01 00:00:00", "%Y-%m-%d %H:%M:%S")))
logs_filtrados = load_objects(device, "access_logs", start_time=start_timestamp)

# Liberar relé
open_relay(device, 1)

# Logout
logout(device)
```

## Uso como Servidor FastAPI

Ejecuta el servidor:
```bash
uvicorn app:app --reload
```

Accede a la documentación interactiva en http://127.0.0.1:8000/docs

### Endpoints

- `POST /devices`: Registrar dispositivo (body: name, ip, login, password)
- `GET /devices`: Listar dispositivos
- `DELETE /devices/{device_id}`: Eliminar dispositivo
- `POST /devices/{device_id}/login`: Login
- `POST /devices/{device_id}/logout`: Logout
- `GET /devices/{device_id}/session`: Verificar sesión
- `GET /devices/{device_id}/objects/{object_name}`: Cargar objetos (users, access_logs, etc.). Para access_logs, por defecto filtra desde el inicio del día actual; opcional query param `start_time` (Unix timestamp) para filtrar desde otra hora.
- `POST /devices/{device_id}/monitor/start`: Iniciar monitoreo automático de logs cada 1 minuto
- `POST /devices/{device_id}/monitor/stop`: Detener monitoreo

## Módulos

- `devices.py`: Gestión de dispositivos y persistencia.
- `auth.py`: Autenticación y manejo de sesiones.
- `objects.py`: Carga y modelado de objetos.
- `controls.py`: Funciones de control (relés, etc.).
- `api.py`: Interfaz principal de la librería.
- `app.py`: Servidor FastAPI.

## Base de Datos

La API incluye una base de datos SQLite (`access_logs.db`) para almacenar logs de acceso de manera persistente. El monitoreo automático guarda solo logs nuevos para evitar duplicados.

## Monitoreo Automático

Puedes iniciar un monitoreo automático que cada 1 minuto:
1. Verifica la sesión del dispositivo.
2. Carga los `access_logs`.
3. Guarda solo los logs nuevos en la base de datos.

Ejemplo:
```bash
curl -X 'POST' 'http://127.0.0.1:8000/devices/1/monitor/start'
```