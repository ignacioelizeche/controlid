"""
push_server.py

Servidor de ejemplo (FastAPI) para soportar polling de dispositivos.
- GET /push/{device_id}           -> devuelve lista de comandos pendientes (por defecto los elimina al entregarlos)
- POST /push/{device_id}/ack      -> acepta ack de ejecución de comandos
- POST /admin/commands            -> encola un comando para un device_id
- GET  /admin/commands/{device_id} -> lista comandos en cola

Autenticación administrativa (opcional): header `X-API-Key` o env var `PUSH_SERVER_API_KEY`.

Instalación (virtualenv):
    pip install fastapi uvicorn

Ejecutar:
    uvicorn push_server:app --host 0.0.0.0 --port 8000

Formato de comando (ejemplo):
{
  "device_id": "device1",
  "action": "open_door",
  "portal_id": 1,
  "duration": 3
}

El servidor mantiene la cola en memoria (no persistente). Adecuado para pruebas locales.
"""
from __future__ import annotations

import os
import uuid
import logging
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Header, Request, APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger('push_server')
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')

# Expose the OpenAPI/Swagger UI under the /controlid prefix so
# the device or external tools can access docs at /controlid/docs
app = FastAPI(
    title='Push Server (example)',
    docs_url='/controlid/docs',
    redoc_url='/controlid/redoc',
    openapi_url='/controlid/openapi.json',
)

# Mount all routes under the /controlid prefix to match device expectations
router = APIRouter(prefix='/controlid')

# API key for admin endpoints. Default 'change-me' but set env var PUSH_SERVER_API_KEY in production.
ADMIN_API_KEY = os.getenv('PUSH_SERVER_API_KEY', 'change-me')

# In-memory queues: device_id -> list[command_dict]
COMMAND_QUEUES: Dict[str, List[Dict[str, Any]]] = {}

# Store a simple ack log in memory for demo/debug
ACK_LOGS: List[Dict[str, Any]] = []


class Command(BaseModel):
    device_id: str
    action: str
    id: Optional[str] = None
    portal_id: Optional[int] = None
    duration: Optional[int] = None
    secbox_id: Optional[int] = None
    relay: Optional[int] = None
    action_id: Optional[str] = None
    endpoint: Optional[str] = None
    method: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None


class Ack(BaseModel):
    command_id: Optional[str]
    status: str
    result: Optional[Any] = None


def require_admin(x_api_key: Optional[str]) -> None:
    if ADMIN_API_KEY and ADMIN_API_KEY != 'change-me':
        if not x_api_key or x_api_key != ADMIN_API_KEY:
            raise HTTPException(status_code=401, detail='Invalid API key')


@router.post('/admin/commands')
async def enqueue_command(cmd: Command, x_api_key: Optional[str] = Header(None)):
    """Encola un comando para un dispositivo (admin).

    Si `id` no está presente, se genera uno.
    """
    require_admin(x_api_key)
    cmd_id = cmd.id or str(uuid.uuid4())
    cmd.id = cmd_id
    q = COMMAND_QUEUES.setdefault(cmd.device_id, [])
    # store as dict
    q.append(cmd.dict())
    logger.info('Command enqueued for device %s id=%s action=%s', cmd.device_id, cmd_id, cmd.action)
    return JSONResponse({'status': 'queued', 'device_id': cmd.device_id, 'command_id': cmd_id})


@router.get('/admin/commands/{device_id}')
async def list_admin_commands(device_id: str, x_api_key: Optional[str] = Header(None)):
    require_admin(x_api_key)
    q = COMMAND_QUEUES.get(device_id, [])
    return {'device_id': device_id, 'queued': q}


@router.get('/push')
async def device_push(deviceId: int = None, uuid: Optional[str] = None, peek: Optional[bool] = False):
    """Endpoint de Pull/Push según especificación.

    Parámetros por query string:
        deviceId: identificador del dispositivo (int)
        uuid: identificador único de la transacción (string)
        peek: si true devuelve la cola sin vaciarla

    Responde con:
      - objeto vacío / JSON vacío cuando no hay comandos
      - un comando simple con campos `verb`, `endpoint`, `body`, `contentType`, `queryString`
      - o un objeto `transactions` que es una lista de comandos con `transactionid` y campos análogos
    """
    if deviceId is None:
        raise HTTPException(status_code=400, detail='deviceId query parameter required')
    device_key = str(deviceId)
    q = COMMAND_QUEUES.get(device_key, [])
    if not q:
        # empty response means no push
        return JSONResponse(content={})
    if peek:
        # return commands as transactions for compatibility
        return {'transactions': q}
    # Pop all commands and return either single or transactions
    commands = q.copy()
    COMMAND_QUEUES[device_key] = []
    logger.info('Delivered %d commands to device %s (uuid=%s)', len(commands), device_key, uuid)
    if len(commands) == 1:
        # map to spec fields
        cmd = commands[0]
        resp = {}
        if 'verb' in cmd:
            resp['verb'] = cmd['verb']
        if 'endpoint' in cmd:
            resp['endpoint'] = cmd['endpoint']
        # the spec expects body as JSON or base64 string depending on contentType
        if 'body' in cmd:
            resp['body'] = cmd['body']
        if 'contentType' in cmd:
            resp['contentType'] = cmd['contentType']
        if 'queryString' in cmd:
            resp['queryString'] = cmd['queryString']
        return resp
    # multiple commands -> transactions
    return {'transactions': commands}


@router.post('/result')
async def device_result(deviceId: int = None, uuid: Optional[str] = None, request: Request = None):
        """Endpoint para recibir el resultado de la ejecución de un push según la especificación.

        Query params:
            - deviceId: id del dispositivo
            - uuid: uuid de la transacción

        El body puede contener:
            - `response`: objeto con resultado de la ejecución (para single command)
            - `error`: string con error
            - `transactions_results`: lista de resultados para cada transactionid
        """
        if deviceId is None:
                raise HTTPException(status_code=400, detail='deviceId query parameter required')
        if uuid is None:
                raise HTTPException(status_code=400, detail='uuid query parameter required')
        payload = await request.json()
        rec = {'device_id': str(deviceId), 'uuid': uuid, 'payload': payload}
        ACK_LOGS.append(rec)
        logger.info('Result received from %s uuid=%s payload_keys=%s', deviceId, uuid, list(payload.keys()))
        # Per spec, response is empty
        return JSONResponse(status_code=200, content={})


@router.delete('/admin/commands/{device_id}/{command_id}')
async def delete_command(device_id: str, command_id: str, x_api_key: Optional[str] = Header(None)):
    require_admin(x_api_key)
    q = COMMAND_QUEUES.get(device_id, [])
    new_q = [c for c in q if c.get('id') != command_id]
    COMMAND_QUEUES[device_id] = new_q
    logger.info('Deleted command %s for device %s', command_id, device_id)
    return {'status': 'deleted', 'command_id': command_id}


@router.get('/admin/ack_logs')
async def get_ack_logs(x_api_key: Optional[str] = Header(None)):
    require_admin(x_api_key)
    return {'ack_logs': ACK_LOGS}


# Register router on the main app so all endpoints are available under /controlid
app.include_router(router)


if __name__ == '__main__':
    import uvicorn

    host = os.getenv('PUSH_SERVER_HOST', '0.0.0.0')
    port = int(os.getenv('PUSH_SERVER_PORT', '8000'))
    uvicorn.run('push_server:app', host=host, port=port, reload=False)
