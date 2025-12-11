# Control iD Access API — Cliente Python

`controlid_client.py` — Cliente oficial en Python para la Control iD Access API.

Este repositorio incluye:
- `controlid_client.py`: cliente REST para la API del dispositivo (sesión, auth, CRUD, helpers).
- `push_server.py`: servidor de ejemplo (FastAPI) para soportar Push (cola en memoria, endpoints `/push` y `/result`).
- `smoke_push.py`: simulador de dispositivo que hace polling a `/push` y ejecuta los comandos recibidos contra el dispositivo usando `ControlIDClient`.

Requisitos
- Python 3.11+
- Dependencias: `requests`, `fastapi`, `uvicorn`, `pydantic` (solo para `push_server`)

Instalación rápida
1. Crear y activar entorno virtual (Windows PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install requests fastapi uvicorn pydantic
```

Uso rápido (cliente)
```python
from controlid_client import ControlIDClient

client = ControlIDClient(
    host='192.168.1.100',
    username='admin',
    password='admin',
    protocol='http',
    cache_ttl=60,
)

# Autenticarse
client.login()

# Listar usuarios (paginado)
users = client.list_users(page=1, per_page=50)
print(users)

# Abrir puerta
client.open_door(portal_id=3, duration=5)

# Cerrar sesión
client.logout()
```

Push (protocolo)
-----------------
Control iD soporta el modo "Push" donde el dispositivo hace polling periódico a un servidor externo para pedir comandos.

Esquema básico:
- Device: realiza `GET /push?deviceId=<id>&uuid=<uuid>` (query string).
- Server: responde con:
  - `{}` ó body vacío -> no hay comandos.
  - Un objeto comando con campos opcionales: `verb`, `endpoint`, `body`, `contentType`, `queryString`.
  - O bien `{"transactions": [ ... ]}` para enviar múltiples comandos en batch.
- Device: ejecuta los comandos y luego POSTea el resultado a `/result?deviceId=<id>&uuid=<uuid>` con el body:
  - Single: `{ "response": ... }`
  - Batch: `{ "transactions_results": [ { transactionid, success, response }, ... ] }`

Ejemplo de respuesta a GET /push (single):
```json
{
  "verb": "POST",
  "endpoint": "set_configuration.fcgi",
  "body": { "general": { "attendance_mode": "1" }, "identifier": { "log_type": "1" } },
  "contentType": "application/json"
}
```

Ejemplo de batch (`transactions`):
```json
{ "transactions": [ { "transactionid": "1", "verb": "POST", "endpoint": "set_configuration", "body": { ... } }, { "transactionid":"2", ... } ] }
```

Archivos de ayuda incluidos
-------------------------
- `push_server.py` — servidor de ejemplo (FastAPI) con endpoints:
  - `GET /push?deviceId=&uuid=` — entrega comandos (según spec).
  - `POST /result?deviceId=&uuid=` — recibe resultados de ejecución (responde vacío).
  - `POST /admin/commands` — encola comando(s) para pruebas.

- `smoke_push.py` — simulador del dispositivo (hace polling a `/push`, ejecuta en el dispositivo y POSTea `/result`).

Cómo ejecutar el servidor Push (pruebas locales)
1. Instalar dependencias (ver arriba).
2. Iniciar server:
```powershell
uvicorn push_server:app --host 0.0.0.0 --port 8000
```

Encolar comandos (admin)
------------------------
Usa `POST /admin/commands` para encolar comandos para un `device_id`. Ejemplo con `curl`:

```powershell
curl -X POST http://localhost:8000/admin/commands -H "Content-Type: application/json" -d '{"device_id":"1001","verb":"POST","endpoint":"set_configuration.fcgi","body":{"general":{"attendance_mode":"1"},"identifier":{"log_type":"1"}},"contentType":"application/json"}'
```

Simular el dispositivo (smoke_push)
---------------------------------
El script `smoke_push.py` actúa como un dispositivo que hace polling y ejecuta comandos:

```powershell
python smoke_push.py --backend http://localhost:8000 --device-id 1001 --device-host 192.168.1.100 --username admin --password admin --poll-interval 3
```

- `--device-host` es la IP del dispositivo Control iD real (el `smoke_push` ejecutará las llamadas a ese equipo usando `ControlIDClient`).
- `--dry-run` imprime las transacciones sin ejecutar y envía resultados simulados al backend.

Ejecutando un comando de "attendance mode"
------------------------------------------
Si quieres activar el modo asistencia, el dispositivo suele aceptar un `POST` a `set_configuration.fcgi` con el payload:

```json
{
  "general": { "attendance_mode": "1" },
  "identifier": { "log_type": "1" }
}
```

Con `ControlIDClient` (ejemplo Python):

```python
payload = {"general": {"attendance_mode": "1"}, "identifier": {"log_type": "1"}}
res = client._post('/set_configuration.fcgi', json=payload)
print(res)
```

Si el firmware requiere `?session=<val>` en la URL, puedes extraer la cookie de la sesión y añadirla:

```python
session_val = client.session.cookies.get('session')
res = client._post(f'/set_configuration.fcgi?session={session_val}', json=payload)
```

Notas de depuración
-------------------
- Si el endpoint devuelve `404`, prueba añadir prefijos como `/api/v1/` antes de `endpoint` o revisa `ControlIDClient.endpoint_map`.
- Si hay `SSL`/cert errors en HTTPS con certificados self-signed, configura `client.session.verify = False` temporalmente.
- Comprueba la cookie `client.session.cookies` después de `login()` para ver si el dispositivo usa cookie o token.

Siguientes pasos recomendados
-----------------------------
- Si quieres, puedo:
  - añadir un helper `set_attendance_mode()` a `ControlIDClient` para encapsular el payload y la llamada;
  - adaptar `smoke_push.py` para mapear ciertos `endpoint` a wrappers (por ejemplo `open_door`, `set_configuration.fcgi` con query `session`);
  - reemplazar la cola en memoria por Redis para persistencia.

Contribuir
----------
- Abrir issues o pull requests con mejoras, mappings reales de endpoints o tests contra dispositivos.

Licencia
-------
- Aquí puedes añadir la licencia que prefieras para tu proyecto.
