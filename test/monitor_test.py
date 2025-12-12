#!/usr/bin/env python3
"""
monitor_test.py

Simple test script that uses the local server API to:
- check device connectivity (via /api/execute getSystemInfo)
- configure the Monitor on the device (via /api/execute setMonitorConfig)
- poll /api/monitor/events and wait for a device_is_alive event

Reads configuration from environment variables or a .env file.
"""
import os
import sys
import time
import json
import logging
from typing import Optional

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

import requests

# Load .env if present and python-dotenv installed
if load_dotenv:
    load_dotenv()

LOG = logging.getLogger('monitor_test')
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# Config
SERVER_HOST = os.getenv('SERVER_HOST', 'localhost')
SERVER_PORT = os.getenv('SERVER_PORT', '3000')
SERVER_BASE = f'http://{SERVER_HOST}:{SERVER_PORT}'
DEVICE_ID = os.getenv('DEVICE_ID', '1')
POLL_TIMEOUT = int(os.getenv('POLL_TIMEOUT', '60'))  # seconds to wait for event
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL', '3'))


def api_execute(command: str, params: dict):
    url = f"{SERVER_BASE}/api/execute"
    payload = {"command": command, "params": params}
    LOG.debug('POST %s %s', url, payload)
    r = requests.post(url, json=payload, timeout=15)
    r.raise_for_status()
    return r.json()


def check_device_connection(device_id: str) -> bool:
    try:
        LOG.info('Checking device connectivity (getSystemInfo)')
        resp = api_execute('getSystemInfo', {'deviceId': device_id})
        if resp.get('success'):
            LOG.info('[OK] Device answered getSystemInfo')
            LOG.debug('systemInfo: %s', json.dumps(resp.get('result'), indent=2))
            return True
        LOG.error('Unexpected response: %s', resp)
    except Exception as e:
        LOG.error('Connection check failed: %s', e)
    return False


def configure_monitor(device_id: str, server_host: str, server_port: str, server_path: str) -> bool:
    monitor = {
        'request_timeout': '5000',
        'hostname': server_host,
        'port': str(server_port),
        'path': server_path.lstrip('/'),
        'alive_interval': '60000',
        'enable_photo_upload': '0',
        'inform_access_event_id': '1'
    }
    LOG.info('Configuring monitor on device %s -> %s:%s/%s', device_id, server_host, server_port, server_path)
    try:
        resp = api_execute('setMonitorConfig', {'deviceId': device_id, 'monitor': monitor})
        if resp.get('success'):
            LOG.info('[OK] Monitor configured (device accepted settings)')
            LOG.debug('device response: %s', json.dumps(resp.get('result'), indent=2))
            return True
        LOG.error('Device returned unexpected response: %s', resp)
    except Exception as e:
        LOG.error('Failed to configure monitor: %s', e)
    return False


def poll_for_event(device_id: str, timeout: int = 60, interval: int = 3) -> Optional[dict]:
    end = time.time() + timeout
    LOG.info('Waiting up to %s seconds for a device_is_alive event...', timeout)
    while time.time() < end:
        try:
            r = requests.get(f"{SERVER_BASE}/api/monitor/events", timeout=10)
            r.raise_for_status()
            events = r.json()
            # events format may be array of rows with path and payload
            for e in events:
                path = e.get('path') or e.get('type')
                payload = e.get('payload') or e.get('data')
                if path and 'device_is_alive' in path:
                    LOG.info('[OK] device_is_alive received: %s', e)
                    return e
                # fallback: check parsed payload
                try:
                    p = json.loads(e.get('payload') or '{}') if e.get('payload') else {}
                    if p.get('device_id') and int(p.get('device_id')) and 'access_logs' in p:
                        # heuristic for alive
                        LOG.info('[OK] device_is_alive-like payload found: %s', p)
                        return e
                except Exception:
                    pass
        except Exception as ex:
            LOG.debug('Error polling events: %s', ex)
        time.sleep(interval)
    LOG.warn('Timeout waiting for event')
    return None


if __name__ == '__main__':
    LOG.info('Monitor test starting')
    if not check_device_connection(DEVICE_ID):
        LOG.error('Device not reachable. Aborting.')
        sys.exit(2)

    # configure monitor to point to this server
    if not configure_monitor(DEVICE_ID, os.getenv('SERVER_HOST', SERVER_HOST), os.getenv('SERVER_PORT', SERVER_PORT), os.getenv('SERVER_PATH', '/api/notifications')):
        LOG.error('Failed to set monitor on device. Aborting.')
        sys.exit(3)

    LOG.info('[WAIT] Waiting for a device_is_alive event (polling)')
    ev = poll_for_event(DEVICE_ID, timeout=POLL_TIMEOUT, interval=POLL_INTERVAL)
    if ev:
        LOG.info('Monitor functioning — event received')
        sys.exit(0)
    else:
        LOG.error('No event received — monitor may not be reaching server')
        sys.exit(4)
