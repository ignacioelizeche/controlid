"""
smoke_push.py

Script de ejemplo que hace polling contra un backend `/push/{device_id}`
para obtener comandos pendientes y los ejecuta en el dispositivo usando
`ControlIDClient` (archivo `controlid_client.py`).

Formato esperado (flexible):
- Lista simple: [ {"id": "cmd1", "action": "open_door", "portal_id": 1, "duration": 3}, ... ]
- Objeto con clave `commands`: {"commands": [ ... ] }

Acciones soportadas (ejemplos):
- `open_door` -> client.open_door(portal_id, duration)
- `trigger_relay` -> client.trigger_relay(secbox_id, relay, duration)
- `run_action` -> client.run_action(action_id, payload)
- `raw` -> ejecuta llamado HTTP directo al dispositivo si `endpoint` y `method` dados.

El script intenta hacer `POST {backend}/push/{device_id}/ack` con el estado de ejecución
para cada comando (si el backend acepta ack). El esquema del ack es flexible.

Uso:
python smoke_push.py --backend http://localhost:8000 --device-id device1 --device-host 192.168.1.100 --username admin --password admin

"""
from __future__ import annotations

import time
import argparse
import json
import logging
from typing import Any, Dict, List, Optional

import requests
from uuid import uuid4
from controlid_client import ControlIDClient, APIError, AuthenticationError

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger('smoke_push')


def fetch_commands(backend: str, device_id: str, uuid: str, auth: Optional[Dict[str, str]] = None, timeout: float = 10.0) -> Dict[str, Any]:
    """Consulta el backend /push según especificación: GET /push?deviceId=..&uuid=..

    Retorna el JSON completo (puede ser vacío, un comando simple o un objeto con `transactions`).
    """
    url = backend.rstrip('/') + f'/push'
    headers = {'Content-Type': 'application/json'}
    if auth and 'api_key' in auth:
        headers['Authorization'] = f"Bearer {auth['api_key']}"
    params = {'deviceId': device_id, 'uuid': uuid}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=timeout)
        r.raise_for_status()
        try:
            data = r.json()
        except Exception:
            logger.warning('Respuesta no-JSON de %s: %s', url, r.text)
            return {}
        return data or {}
    except requests.RequestException as e:
        logger.error('Error contactando backend %s: %s', url, e)
        return {}


def post_result(backend: str, device_id: str, uuid: str, payload: Dict[str, Any], auth: Optional[Dict[str, str]] = None) -> None:
    """Envía el resultado de la ejecución al backend según especificación:

    POST /result?deviceId=..&uuid=..
    Body: puede contener `response` o `transactions_results` o `error`.
    """
    url = backend.rstrip('/') + f'/result'
    headers = {'Content-Type': 'application/json'}
    if auth and 'api_key' in auth:
        headers['Authorization'] = f"Bearer {auth['api_key']}"
    params = {'deviceId': device_id, 'uuid': uuid}
    try:
        r = requests.post(url, json=payload, headers=headers, params=params, timeout=8)
        try:
            r.raise_for_status()
            logger.debug('Result posted for uuid=%s', uuid)
        except requests.RequestException:
            logger.warning('No se pudo post result uuid=%s: %s %s', uuid, r.status_code, r.text)
    except requests.RequestException as e:
        logger.error('Error enviando result a backend: %s', e)


def execute_command(client: ControlIDClient, cmd: Dict[str, Any]) -> Dict[str, Any]:
    """Ejecuta un comando usando `ControlIDClient`.

    Devuelve un dict con keys `ok` (bool) y `result` (respuesta o mensaje de error).
    """
    action = cmd.get('action')
    cid = cmd.get('id') or cmd.get('command_id') or '<no-id>'
    logger.info('Ejecutando comando %s action=%s', cid, action)
    try:
        if action == 'open_door':
            portal_id = cmd.get('portal_id')
            duration = int(cmd.get('duration', 5))
            if portal_id is None:
                raise ValueError('portal_id requerido')
            res = client.open_door(portal_id, duration=duration)
            return {'ok': True, 'result': res}

        if action == 'trigger_relay':
            secbox_id = cmd.get('secbox_id')
            relay = int(cmd.get('relay', 1))
            duration = int(cmd.get('duration', 1))
            if secbox_id is None:
                raise ValueError('secbox_id requerido')
            res = client.trigger_relay(secbox_id, relay=relay, duration=duration)
            return {'ok': True, 'result': res}

        if action == 'run_action':
            action_id = cmd.get('action_id') or cmd.get('id_action')
            payload = cmd.get('payload')
            if action_id is None:
                raise ValueError('action_id requerido')
            res = client.run_action(action_id, payload)
            return {'ok': True, 'result': res}

        if action == 'raw':
            # Ejecuta un llamado directo al dispositivo: method, endpoint, payload
            method = (cmd.get('method') or 'POST').upper()
            endpoint = cmd.get('endpoint')
            payload = cmd.get('payload')
            if not endpoint:
                raise ValueError('endpoint requerido para raw')
            logger.debug('raw call %s %s', method, endpoint)
            # _request acepta method via helper mapping
            if method == 'GET':
                res = client._get(endpoint, params=payload)
            elif method == 'POST':
                res = client._post(endpoint, json=payload)
            elif method == 'PUT':
                res = client._put(endpoint, json=payload)
            elif method == 'DELETE':
                res = client._delete(endpoint, json=payload)
            else:
                raise ValueError(f'Method {method} not supported')
            return {'ok': True, 'result': res}

        # fallback: support `create_user`, etc. Map basic CRUD generically
        if action in ('create_user', 'create_card', 'create_pin'):
            # determine resource
            if action == 'create_user':
                res = client.create_user(cmd.get('payload', {}))
            elif action == 'create_card':
                res = client.create_card(cmd.get('payload', {}))
            else:
                res = client.create_pin(cmd.get('payload', {}))
            return {'ok': True, 'result': res}

        raise ValueError(f'Acción no soportada: {action}')

    except AuthenticationError as e:
        logger.error('AuthenticationError: %s', e)
        return {'ok': False, 'result': f'Auth error: {e}'}
    except APIError as e:
        logger.error('APIError: %s (status=%s) body=%s', e, getattr(e, 'status_code', None), getattr(e, 'body', None))
        return {'ok': False, 'result': {'error': str(e), 'status': getattr(e, 'status_code', None), 'body': getattr(e, 'body', None)}}
    except Exception as e:
        logger.exception('Error ejecutando comando %s: %s', cid, e)
        return {'ok': False, 'result': str(e)}


def main() -> None:
    parser = argparse.ArgumentParser(description='Polling bridge: backend -> device (ControlID)')
    parser.add_argument('--backend', required=True, help='URL base del backend (ej. http://localhost:8000)')
    parser.add_argument('--device-id', required=True, help='ID del dispositivo que hace polling')
    parser.add_argument('--device-host', required=True, help='IP/host del dispositivo (Control iD)')
    parser.add_argument('--username', required=True, help='Usuario del dispositivo')
    parser.add_argument('--password', required=True, help='Password del dispositivo')
    parser.add_argument('--protocol', default='http', help='http o https')
    parser.add_argument('--poll-interval', type=int, default=5, help='Segundos entre polls')
    parser.add_argument('--backend-api-key', default=None, help='Bearer token para backend si aplica')
    parser.add_argument('--dry-run', action='store_true', help='No ejecuta los comandos, solo los imprime')

    args = parser.parse_args()

    auth = None
    if args.backend_api_key:
        auth = {'api_key': args.backend_api_key}

    client = ControlIDClient(host=args.device_host, username=args.username, password=args.password, protocol=args.protocol)

    # Intentar login inicial
    try:
        logger.info('Intentando login en dispositivo %s', args.device_host)
        client.login()
    except Exception as e:
        logger.warning('Login inicial falló: %s. El script intentará re-autenticar antes de ejecutar comandos.', e)

    logger.info('Iniciando loop de polling: backend=%s device=%s interval=%ds', args.backend, args.device_id, args.poll_interval)
    while True:
        try:
            # generate uuid for this poll (device sends uuid in its GET request)
            poll_uuid = str(uuid4())
            data = fetch_commands(args.backend, args.device_id, poll_uuid, auth=auth)
            if not data:
                logger.debug('No hay comandos, durmiendo %ds', args.poll_interval)
                time.sleep(args.poll_interval)
                continue

            # decide if we have transactions or a single command
            if 'transactions' in data and isinstance(data['transactions'], list):
                transactions = data['transactions']
            else:
                # single command; wrap into a list of one transaction
                # the spec uses keys verb, endpoint, body, contentType, queryString
                transactions = [data]

            # dry-run handling
            if args.dry_run:
                logger.info('[dry-run] transactions: %s', json.dumps(transactions, default=str))
                # send an empty transactions_results where each transaction is success:true
                tr_results = []
                for tx in transactions:
                    trid = tx.get('transactionid') or tx.get('transactionid') or '1'
                    tr_results.append({'transactionid': trid, 'success': True, 'response': {}})
                post_result(args.backend, args.device_id, poll_uuid, {'transactions_results': tr_results}, auth=auth)
                time.sleep(args.poll_interval)
                continue

            # ensure auth to device
            try:
                if not client.token:
                    logger.info('Token ausente, reintentando login...')
                    client.login()
            except Exception as e:
                logger.error('No se pudo autenticar antes de ejecutar comandos: %s', e)
                # Report error for all transactions
                tr_results = []
                for tx in transactions:
                    trid = tx.get('transactionid') or tx.get('transactionid') or '1'
                    tr_results.append({'transactionid': trid, 'success': False, 'response': f'auth_failed: {e}'})
                post_result(args.backend, args.device_id, poll_uuid, {'transactions_results': tr_results}, auth=auth)
                time.sleep(args.poll_interval)
                continue

            # Execute each transaction and collect results
            tr_results = []
            for tx in transactions:
                trid = tx.get('transactionid') or tx.get('transactionid') or str(tx.get('id') or '') or '1'
                try:
                    # If transaction uses 'endpoint' + 'verb', perform call to device API
                    verb = (tx.get('verb') or 'POST').upper()
                    endpoint = tx.get('endpoint')
                    body = tx.get('body')
                    query_string = tx.get('queryString')
                    if endpoint:
                        # call device endpoint directly
                        if verb == 'GET':
                            res = client._get(f"/{endpoint}", params=query_string or body)
                        elif verb == 'POST':
                            res = client._post(f"/{endpoint}", json=body)
                        elif verb == 'PUT':
                            res = client._put(f"/{endpoint}", json=body)
                        elif verb == 'DELETE':
                            res = client._delete(f"/{endpoint}", json=body)
                        else:
                            raise ValueError(f'Unsupported verb: {verb}')
                        tr_results.append({'transactionid': trid, 'success': True, 'response': res})
                    else:
                        # fallback to execute_command (legacy action-based commands)
                        result = execute_command(client, tx)
                        if result.get('ok'):
                            tr_results.append({'transactionid': trid, 'success': True, 'response': result.get('result')})
                        else:
                            tr_results.append({'transactionid': trid, 'success': False, 'response': result.get('result')})
                except Exception as e:
                    logger.exception('Error executing transaction %s: %s', trid, e)
                    tr_results.append({'transactionid': trid, 'success': False, 'response': str(e)})

            # Post batch results according to spec
            post_result(args.backend, args.device_id, poll_uuid, {'transactions_results': tr_results}, auth=auth)

        except Exception as e:
            logger.exception('Error en loop principal: %s', e)

        time.sleep(args.poll_interval)


if __name__ == '__main__':
    main()
