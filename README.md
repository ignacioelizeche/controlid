# Control iD Access API — Cliente Python

`controlid_client.py` — Cliente oficial en Python para la Control iD Access API.

Requisitos
- Python 3.11+
- Dependencia: `requests`

Instalación
1. Crear un entorno virtual (opcional):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install requests
```

Uso rápido
```python
from controlid_client import ControlIDClient

client = ControlIDClient(
    host='192.168.1.100',
    username='admin',
    password='admin',
    protocol='http',
    cache_ttl=60,   # cache opcional en segundos
)

# Autenticarse
client.login()

# Listar usuarios (paginado)
users = client.list_users(page=1, per_page=50)
print(users)

# Crear usuario
new = client.create_user({'name': 'Juan Perez', 'card_number': '123456'})
print(new)

# Abrir puerta
client.open_door(portal_id=3, duration=5)

# Consultar logs de acceso desde/hasta (según soporte del dispositivo)
logs = client.get_access_logs(start_time='2025-12-01T00:00:00Z', end_time='2025-12-10T23:59:59Z', per_page=200)
print(len(logs))

# Cerrar sesión
client.logout()
```

Principales funcionalidades
- Clase principal: `ControlIDClient` con manejo de sesión (cookies y tokens).
- Métodos HTTP genéricos: `_get`, `_post`, `_put`, `_delete`.
- CRUD y wrappers explícitos para recursos comunes: `users`, `cards`, `pins`, `templates`, `qrcodes`, `uhf_tags`, `groups`, `areas`, `portals`, `access_rules`, `time_zones`, `alarm_zones`, `devices`, `sec_boxs`, `contacts`, `network_interlocking_rules`, `custom_thresholds`, etc.
- Métodos especiales:
  - Logs: `get_access_logs()`, `get_alarm_logs()`, `get_event_logs()`
  - Control físico: `open_door()`, `trigger_relay()`
  - Sincronización de plantillas: `template_sync_init()`, `template_sync_end()`
  - Programaciones: `list_scheduled_unlocks()`, `create_scheduled_unlock()`
  - Auditoría: `get_change_logs()`
- Paginación y filtros en `load_objects()` (parámetros `page`, `per_page`, `filters`).
- Validaciones mínimas de campos requeridos con `_validate_required()`.
- Caché local en memoria configurable vía `cache_ttl`.
- Soporte multi-dispositivo: `switch_device()` y tokens por host.

Notas de implementación
- `endpoint_map` contiene el mapeo lógico→ruta. Si la versión del dispositivo usa rutas distintas (prefijos, versiones), actualice `ControlIDClient.endpoint_map` para que apunte a las rutas reales del API del equipo.
- El método `login()` busca un `token` en el JSON de respuesta o en el header `Authorization`. Si la API usa cookies o esquema distinto, adapte `login()` y `_request()` para mantener el estado apropiado.
- Por defecto, `ControlIDClient` lanza excepciones (`APIError`, `AuthenticationError`, `NotFoundError`) si la respuesta HTTP tiene código >= 400. Cambie `raise_on_error=False` si prefiere manejar manualmente los códigos de error.

Sugerencias y siguientes pasos
- Si me proporcionas ejemplos reales de endpoints/respuestas (ej. `POST /login` respuesta JSON, paths exactos), adapto `endpoint_map` y las rutas especiales (`/templates/sync/*`, `/portals/{id}/open`, etc.).
- Puedo añadir validación avanzada con `pydantic` o pruebas unitarias (`pytest`) y un pequeño script de smoke-test que pruebe login, listado y apertura de puerta.
- Para caching en producción o entornos distribuidos, integrar Redis o similar.

Contribuir
- Abrir issues o pull requests con mejoras, mapping de endpoints reales o tests contra dispositivos.

Licencia
- Aquí puedes añadir la licencia que prefieras para tu proyecto.
