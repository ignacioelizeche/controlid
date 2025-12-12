# Control ID API

API modular en Python para interactuar con dispositivos de Control ID usando REST/HTTP POST con JSON.

## Instalación

1. Crea un entorno virtual:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # En Windows
   ```

2. Instala dependencias:
   ```bash
   pip install -r requirements.txt
   ```

## Uso como Librería

```python
from api import add_device, get_device, login, load_objects, logout, open_relay

# Registrar dispositivo
add_device("192.168.100.22", "admin", "password")

# Obtener dispositivo
device = get_device("192.168.100.22")

# Login
login(device)

# Cargar objetos
logs = load_objects(device, "access_logs")
users = load_objects(device, "users")

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

- `POST /devices`: Registrar dispositivo
- `GET /devices`: Listar dispositivos
- `DELETE /devices/{ip}`: Eliminar dispositivo
- `POST /devices/{ip}/login`: Login
- `POST /devices/{ip}/logout`: Logout
- `GET /devices/{ip}/session`: Verificar sesión
- `GET /devices/{ip}/objects/{object_name}`: Cargar objetos
- `POST /devices/{ip}/control/relay`: Liberar relé

## Módulos

- `devices.py`: Gestión de dispositivos y persistencia.
- `auth.py`: Autenticación y manejo de sesiones.
- `objects.py`: Carga y modelado de objetos.
- `controls.py`: Funciones de control (relés, etc.).
- `api.py`: Interfaz principal de la librería.
- `app.py`: Servidor FastAPI.

## Extensión

Para agregar nuevos objetos, define una dataclass en `objects.py` y agrégala al diccionario `OBJECT_CLASSES`.

Para nuevas funcionalidades, agrega funciones en los módulos correspondientes y endpoints en `app.py`.