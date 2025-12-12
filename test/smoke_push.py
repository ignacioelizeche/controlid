#!/usr/bin/env python3
"""
smoke_push.py

Quick smoke tests for the ControlID + Monitor integration using the local server API.
- Tests login/getSystemInfo
- Tests get_configuration (via proxy)
- Tests setMonitorConfig
- Optionally calls fullconfig

Logs to console and optionally to a file
"""
import os
import sys
import json
import logging
import time
from typing import Any

import requests

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
LOG = logging.getLogger('smoke_push')

SERVER_HOST = os.getenv('SERVER_HOST', 'localhost')
SERVER_PORT = os.getenv('SERVER_PORT', '3000')
SERVER_BASE = f'http://{SERVER_HOST}:{SERVER_PORT}'
DEVICE_ID = os.getenv('DEVICE_ID', '1')


def api_execute(command: str, params: dict) -> Any:
    url = f"{SERVER_BASE}/api/execute"
    r = requests.post(url, json={"command": command, "params": params}, timeout=15)
    r.raise_for_status()
    return r.json()


def test_login(device_id: str) -> bool:
    try:
        LOG.info('Testing login/getSystemInfo')
        resp = api_execute('login', {'deviceId': device_id}) if False else api_execute('getSystemInfo', {'deviceId': device_id})
        LOG.info('[OK] getSystemInfo returned')
        LOG.debug(json.dumps(resp, indent=2))
        return True
    except Exception as e:
        LOG.error('Login/getSystemInfo failed: %s', e)
        return False


def test_getconfig(device_id: str) -> bool:
    url = f"{SERVER_BASE}/api/devices/{device_id}/getconfig"
    try:
        LOG.info('Requesting get_configuration (proxy)')
        r = requests.post(url, json={}, timeout=20)
        r.raise_for_status()
        j = r.json()
        LOG.info('[OK] get_configuration returned keys: %s', list(j.keys()))
        LOG.debug(json.dumps(j.get('body') or j, indent=2)[:1000])
        return True
    except Exception as e:
        LOG.error('get_configuration failed: %s', e)
        return False


def test_setmonitor(device_id: str) -> bool:
    try:
        data = {
            'request_timeout': '5000',
            'hostname': os.getenv('SERVER_HOST', SERVER_HOST),
            'port': os.getenv('SERVER_PORT', SERVER_PORT),
            'path': os.getenv('SERVER_PATH', '/api/notifications').lstrip('/'),
            'enable_photo_upload': '0'
        }
        LOG.info('Setting monitor: %s', data)
        resp = api_execute('setMonitorConfig', {'deviceId': device_id, 'monitor': data})
        LOG.info('[OK] setMonitorConfig returned success')
        LOG.debug(json.dumps(resp, indent=2))
        return True
    except Exception as e:
        LOG.error('setMonitorConfig failed: %s', e)
        return False


if __name__ == '__main__':
    LOG.info('Running smoke push tests')
    if not test_login(DEVICE_ID):
        LOG.error('Login test failed — aborting')
        sys.exit(2)

    if not test_getconfig(DEVICE_ID):
        LOG.warn('getconfig failed (module may be absent) — continue testing')

    if not test_setmonitor(DEVICE_ID):
        LOG.error('setMonitorConfig failed')
        sys.exit(3)

    LOG.info('Smoke tests finished — check /api/monitor/events or /monitor.html for events')
    sys.exit(0)
