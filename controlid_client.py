"""
controlid_client.py

Client oficial para la Control iD Access API.

Requisitos: Python 3.11+

Uso rapido:
    from controlid_client import ControlIDClient
    client = ControlIDClient(host='192.168.1.100', username='admin', password='admin')
    client.login()
    users = client.list_users()

Este módulo proporciona:
- Clase `ControlIDClient` con manejo de sesión (cookies / token)
- Métodos CRUD para los recursos soportados
- Métodos especiales: logs, control de puertas, sincronización de plantillas, etc.

Nota: Esta es una implementación genérica y está pensada para ser plug-and-play;
adapte `endpoint_map` si la API del dispositivo tiene rutas diferentes.
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional, Iterable, Mapping, Tuple
import requests
from requests import Response
from urllib.parse import urljoin
from dataclasses import dataclass


class ControlIDError(Exception):
    """Base exception for Control iD client errors."""


class AuthenticationError(ControlIDError):
    """Raised when authentication fails or no session exists."""


class NotFoundError(ControlIDError):
    """Raised when a resource is not found (HTTP 404)."""


class APIError(ControlIDError):
    """Raised for API-specific error responses.

    Attributes:
        status_code: HTTP response status code
        body: Decoded JSON body or raw text
    """

    def __init__(self, message: str, status_code: Optional[int] = None, body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


@dataclass
class DeviceInfo:
    """Informal record to store per-device connection options."""
    host: str
    port: Optional[int] = None
    base_path: str = '/'
    protocol: str = 'http'

    def base_url(self) -> str:
        port_part = f":{self.port}" if self.port else ''
        return f"{self.protocol}://{self.host}{port_part}{self.base_path}"


class ControlIDClient:
    """Cliente para Control iD Access API.

    Parámetros:
        host: IP o hostname del dispositivo
        username: usuario para autenticación
        password: contraseña para autenticación
        protocol: 'http' o 'https'
        port: puerto opcional
        timeout: tiempo en segundos para las requests
        cache_ttl: si >0, cache local en memoria por esta cantidad de segundos
        raise_on_error: si True lanza excepciones en respuestas HTTP >=400

    Ejemplo:
        client = ControlIDClient('192.168.1.10', 'admin', '1234')
        client.login()
        users = client.list_users(page=1, per_page=100)
    """

    # Mapa por defecto de endpoints; si la API cambia, actualice estas rutas
    endpoint_map = {
        # Usuarios y grupos
        'users': 'users',
        'groups': 'groups',
        'user_groups': 'user-groups',
        'user_roles': 'user-roles',

        # Credenciales
        'cards': 'cards',
        'pins': 'pins',
        'templates': 'templates',
        'qrcodes': 'qrcodes',
        'uhf_tags': 'uhf-tags',

        # Areas / Portales
        'areas': 'areas',
        'portals': 'portals',
        'portal_actions': 'portal-actions',

        # Reglas de acceso
        'access_rules': 'access-rules',
        'portal_access_rules': 'portal-access-rules',
        'group_access_rules': 'group-access-rules',
        'user_access_rules': 'user-access-rules',
        'area_access_rules': 'area-access-rules',

        # Horarios y zonas de tiempo
        'time_zones': 'time-zones',
        'time_spans': 'time-spans',
        'holidays': 'holidays',
        'access_rule_time_zones': 'access-rule-time-zones',
        'alarm_zone_time_zones': 'alarm-zone-time-zones',

        # Alarmas
        'alarm_zones': 'alarm-zones',
        'alarm_logs': 'alarm-logs',
        'timed_alarms': 'timed-alarms',

        # Contingencias
        'contingency_cards': 'contingency-cards',
        'contingency_card_access_rules': 'contingency-card-access-rules',

        # Eventos y logs
        'access_logs': 'access-logs',
        'access_events': 'access-events',
        'catra_infos': 'catra-infos',
        'log_types': 'log-types',

        # Actions/Scripts
        'actions': 'actions',

        # Dispositivos
        'devices': 'devices',
        'sec_boxs': 'sec-boxs',

        # SIP/Intercom
        'contacts': 'contacts',

        # Network interlocking
        'network_interlocking_rules': 'network-interlocking-rules',

        # Reconocimiento
        'custom_thresholds': 'custom-thresholds',
    }

    def __init__(
        self,
        host: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        protocol: str = 'http',
        port: Optional[int] = None,
        timeout: float = 10.0,
        cache_ttl: int = 0,
        raise_on_error: bool = True,
    ) -> None:
        self.device = DeviceInfo(host=host, port=port, protocol=protocol)
        self.username = username
        self.password = password
        self.timeout = timeout
        self.session = requests.Session()
        self.token: Optional[str] = None
        self.cached_at: Dict[str, float] = {}
        self.cache: Dict[str, Any] = {}
        self.cache_ttl = cache_ttl
        self.raise_on_error = raise_on_error
        # Allow multiple device sessions by tracking per-host token if needed
        self.multi_device_tokens: Dict[str, str] = {}

    # ----------------------------- Utilities -----------------------------
    def _url(self, path: str, host: Optional[str] = None) -> str:
        """Construye la URL completa para una ruta relativa dada.

        Si `path` es una URL absoluta, la retorna tal cual.
        """
        if path.startswith('http://') or path.startswith('https://'):
            return path
        base = self.device.base_url() if host is None else DeviceInfo(host=host).base_url()
        return urljoin(base, path.lstrip('/'))

    def _raise_for_status(self, resp: Response) -> None:
        if resp.status_code == 401:
            raise AuthenticationError('No autorizado o sesión expirada')
        if resp.status_code == 404:
            raise NotFoundError('Recurso no encontrado')
        if resp.status_code >= 400:
            body = None
            try:
                body = resp.json()
            except Exception:
                body = resp.text
            raise APIError(f'HTTP {resp.status_code}: {resp.reason}', status_code=resp.status_code, body=body)

    def _apply_cache(self, key: str, value: Any) -> None:
        if self.cache_ttl <= 0:
            return
        self.cache[key] = value
        self.cached_at[key] = time.time()

    def _get_cache(self, key: str) -> Optional[Any]:
        if self.cache_ttl <= 0:
            return None
        at = self.cached_at.get(key)
        if not at:
            return None
        if time.time() - at > self.cache_ttl:
            self.cache.pop(key, None)
            self.cached_at.pop(key, None)
            return None
        return self.cache.get(key)

    # ----------------------------- Auth ----------------------------------
    def login(self, host: Optional[str] = None) -> Dict[str, Any]:
        """Inicia sesión en el dispositivo.

        Realiza la autenticación con `username` y `password` y guarda cookies / token.

        Args:
            host: host alternativo para multi-device (opcional)

        Returns:
            El JSON de respuesta de login.

        Raises:
            AuthenticationError si falla la autenticación.
        """
        if not self.username or not self.password:
            raise AuthenticationError('Se requiere username y password para login')
        path = '/login'
        url = self._url(path, host=host)
        payload = {'username': self.username, 'password': self.password}
        resp = self.session.post(url, json=payload, timeout=self.timeout)
        if resp.status_code >= 400:
            self._raise_for_status(resp)
        data = resp.json() if resp.content else {}
        # Soporte para token en respuesta
        token = data.get('token') or resp.headers.get('Authorization')
        if token:
            self.token = token
            if host:
                self.multi_device_tokens[host] = token
            # set header for future requests
            self.session.headers.update({'Authorization': f'Bearer {token}'})
        return data

    def logout(self, host: Optional[str] = None) -> None:
        """Cierra la sesión en el dispositivo y limpia el token localmente."""
        try:
            url = self._url('/logout', host=host)
            self.session.post(url, timeout=self.timeout)
        except Exception:
            # Ignorar fallos en logout remoto
            pass
        if host and host in self.multi_device_tokens:
            self.multi_device_tokens.pop(host, None)
        self.token = None
        # limpiar headers
        for h in ('Authorization',):
            self.session.headers.pop(h, None)

    # ----------------------------- HTTP Wrappers -------------------------
    def _request(
        self, method: str, path: str, *, params: Optional[Mapping[str, Any]] = None,
        json: Optional[Any] = None, host: Optional[str] = None, headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None
    ) -> Any:
        """Llama al endpoint y retorna JSON decodificado o texto.

        Lanza excepciones en caso de error HTTP.
        """
        url = self._url(path, host=host)
        hdrs = {} if headers is None else dict(headers)
        if self.token and 'Authorization' not in hdrs:
            hdrs['Authorization'] = f'Bearer {self.token}'
        to = timeout or self.timeout
        resp = self.session.request(method, url, params=params, json=json, headers=hdrs, timeout=to)
        if resp.status_code >= 400:
            if self.raise_on_error:
                self._raise_for_status(resp)
        try:
            return resp.json()
        except Exception:
            return resp.text

    def _get(self, path: str, **kwargs) -> Any:
        return self._request('GET', path, **kwargs)

    def _post(self, path: str, **kwargs) -> Any:
        return self._request('POST', path, **kwargs)

    def _put(self, path: str, **kwargs) -> Any:
        return self._request('PUT', path, **kwargs)

    def _delete(self, path: str, **kwargs) -> Any:
        return self._request('DELETE', path, **kwargs)

    # ----------------------------- Validators ---------------------------
    def _validate_required(self, data: Mapping[str, Any], required: Iterable[str]) -> None:
        missing = [k for k in required if k not in data or data[k] in (None, '')]
        if missing:
            raise ValueError(f'Faltan campos requeridos: {missing}')

    # ----------------------------- Generic CRUD -------------------------
    def load_objects(self, resource: str, *, page: Optional[int] = None, per_page: Optional[int] = None,
                     filters: Optional[Mapping[str, Any]] = None, host: Optional[str] = None) -> Any:
        """Lista objetos de un recurso con paginación y filtros.

        - `resource` es la llave en `endpoint_map`.
        - `filters` es un dict con parámetros de consulta.
        """
        if resource not in self.endpoint_map:
            raise ValueError('Recurso desconocido: ' + resource)
        params = {} if filters is None else dict(filters)
        if page is not None:
            params.setdefault('page', page)
        if per_page is not None:
            params.setdefault('per_page', per_page)
        path = f"/{self.endpoint_map[resource]}"
        cache_key = f"list:{resource}:{str(params)}:{host}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached
        data = self._get(path, params=params, host=host)
        self._apply_cache(cache_key, data)
        return data

    def create_object(self, resource: str, payload: Mapping[str, Any], *, host: Optional[str] = None) -> Any:
        """Crea un objeto en el recurso indicado."""
        if resource not in self.endpoint_map:
            raise ValueError('Recurso desconocido: ' + resource)
        path = f"/{self.endpoint_map[resource]}"
        return self._post(path, json=payload, host=host)

    def get_object(self, resource: str, object_id: Any, *, host: Optional[str] = None) -> Any:
        if resource not in self.endpoint_map:
            raise ValueError('Recurso desconocido: ' + resource)
        path = f"/{self.endpoint_map[resource]}/{object_id}"
        return self._get(path, host=host)

    def update_object(self, resource: str, object_id: Any, payload: Mapping[str, Any], *, host: Optional[str] = None) -> Any:
        if resource not in self.endpoint_map:
            raise ValueError('Recurso desconocido: ' + resource)
        path = f"/{self.endpoint_map[resource]}/{object_id}"
        return self._put(path, json=payload, host=host)

    def delete_object(self, resource: str, object_id: Any, *, host: Optional[str] = None) -> Any:
        if resource not in self.endpoint_map:
            raise ValueError('Recurso desconocido: ' + resource)
        path = f"/{self.endpoint_map[resource]}/{object_id}"
        return self._delete(path, host=host)

    # ----------------------------- Generar wrappers por recurso ---------
    # Para mantener el archivo legible, se generan métodos con nombres explícitos
    # que llaman a los métodos genéricos. Esto asegura cobertura para todos los
    # objetos solicitados sin duplicar lógica de red.

    # Usuarios
    def list_users(self, **kwargs):
        return self.load_objects('users', **kwargs)

    def create_user(self, payload: Mapping[str, Any], **kwargs):
        # Validación mínima
        self._validate_required(payload, ['name'])
        return self.create_object('users', payload, **kwargs)

    def get_user(self, user_id: Any, **kwargs):
        return self.get_object('users', user_id, **kwargs)

    def update_user(self, user_id: Any, payload: Mapping[str, Any], **kwargs):
        return self.update_object('users', user_id, payload, **kwargs)

    def delete_user(self, user_id: Any, **kwargs):
        return self.delete_object('users', user_id, **kwargs)

    # Credenciales: cards, pins, templates, qrcodes, uhf_tags
    def list_cards(self, **kwargs):
        return self.load_objects('cards', **kwargs)

    def create_card(self, payload: Mapping[str, Any], **kwargs):
        self._validate_required(payload, ['card_number'])
        return self.create_object('cards', payload, **kwargs)

    def get_card(self, card_id: Any, **kwargs):
        return self.get_object('cards', card_id, **kwargs)

    def update_card(self, card_id: Any, payload: Mapping[str, Any], **kwargs):
        return self.update_object('cards', card_id, payload, **kwargs)

    def delete_card(self, card_id: Any, **kwargs):
        return self.delete_object('cards', card_id, **kwargs)

    def list_pins(self, **kwargs):
        return self.load_objects('pins', **kwargs)

    def create_pin(self, payload: Mapping[str, Any], **kwargs):
        self._validate_required(payload, ['pin'])
        return self.create_object('pins', payload, **kwargs)

    def list_templates(self, **kwargs):
        return self.load_objects('templates', **kwargs)

    def upload_template(self, payload: Mapping[str, Any], **kwargs):
        self._validate_required(payload, ['user_id', 'template'])
        return self.create_object('templates', payload, **kwargs)

    def list_qrcodes(self, **kwargs):
        return self.load_objects('qrcodes', **kwargs)

    def create_qrcode(self, payload: Mapping[str, Any], **kwargs):
        self._validate_required(payload, ['code'])
        return self.create_object('qrcodes', payload, **kwargs)

    def list_uhf_tags(self, **kwargs):
        return self.load_objects('uhf_tags', **kwargs)

    def create_uhf_tag(self, payload: Mapping[str, Any], **kwargs):
        self._validate_required(payload, ['epc'])
        return self.create_object('uhf_tags', payload, **kwargs)

    # Grupos y roles
    def list_groups(self, **kwargs):
        return self.load_objects('groups', **kwargs)

    def create_group(self, payload: Mapping[str, Any], **kwargs):
        self._validate_required(payload, ['name'])
        return self.create_object('groups', payload, **kwargs)

    def list_user_groups(self, **kwargs):
        return self.load_objects('user_groups', **kwargs)

    def list_user_roles(self, **kwargs):
        return self.load_objects('user_roles', **kwargs)

    # Areas y portales
    def list_areas(self, **kwargs):
        return self.load_objects('areas', **kwargs)

    def create_area(self, payload: Mapping[str, Any], **kwargs):
        self._validate_required(payload, ['name'])
        return self.create_object('areas', payload, **kwargs)

    def list_portals(self, **kwargs):
        return self.load_objects('portals', **kwargs)

    def create_portal(self, payload: Mapping[str, Any], **kwargs):
        self._validate_required(payload, ['name'])
        return self.create_object('portals', payload, **kwargs)

    def list_portal_actions(self, **kwargs):
        return self.load_objects('portal_actions', **kwargs)

    # Access rules
    def list_access_rules(self, **kwargs):
        return self.load_objects('access_rules', **kwargs)

    def create_access_rule(self, payload: Mapping[str, Any], **kwargs):
        self._validate_required(payload, ['name'])
        return self.create_object('access_rules', payload, **kwargs)

    # Time zones / schedules
    def list_time_zones(self, **kwargs):
        return self.load_objects('time_zones', **kwargs)

    def create_time_zone(self, payload: Mapping[str, Any], **kwargs):
        self._validate_required(payload, ['name'])
        return self.create_object('time_zones', payload, **kwargs)

    def list_time_spans(self, **kwargs):
        return self.load_objects('time_spans', **kwargs)

    def list_holidays(self, **kwargs):
        return self.load_objects('holidays', **kwargs)

    # Alarmas
    def list_alarm_zones(self, **kwargs):
        return self.load_objects('alarm_zones', **kwargs)

    def list_alarm_logs(self, **kwargs):
        return self.load_objects('alarm_logs', **kwargs)

    # Contingencia
    def list_contingency_cards(self, **kwargs):
        return self.load_objects('contingency_cards', **kwargs)

    # Eventos / logs
    def list_access_logs(self, **kwargs):
        return self.load_objects('access_logs', **kwargs)

    def get_access_logs(self, *, start_time: Optional[str] = None, end_time: Optional[str] = None, **kwargs):
        """Consulta logs de acceso con filtros de tiempo.

        start_time/end_time en formato ISO o según lo que acepte el dispositivo.
        """
        filters = kwargs.pop('filters', {}) or {}
        if start_time:
            filters['start_time'] = start_time
        if end_time:
            filters['end_time'] = end_time
        return self.load_objects('access_logs', filters=filters, **kwargs)

    def get_alarm_logs(self, *, start_time: Optional[str] = None, end_time: Optional[str] = None, **kwargs):
        filters = kwargs.pop('filters', {}) or {}
        if start_time:
            filters['start_time'] = start_time
        if end_time:
            filters['end_time'] = end_time
        return self.load_objects('alarm_logs', filters=filters, **kwargs)

    def get_event_logs(self, **kwargs):
        return self.load_objects('access_events', **kwargs)

    # Actions and scripts
    def run_action(self, action_id: Any, payload: Optional[Mapping[str, Any]] = None, **kwargs):
        path = f"/{self.endpoint_map.get('actions','actions')}/{action_id}/run"
        return self._post(path, json=payload, **kwargs)

    # Dispositivos
    def list_devices(self, **kwargs):
        return self.load_objects('devices', **kwargs)

    # SecBox / relays
    def list_sec_boxs(self, **kwargs):
        return self.load_objects('sec_boxs', **kwargs)

    # Contacts (SIP)
    def list_contacts(self, **kwargs):
        return self.load_objects('contacts', **kwargs)

    # Network interlocking rules
    def list_network_interlocking_rules(self, **kwargs):
        return self.load_objects('network_interlocking_rules', **kwargs)

    # Custom thresholds
    def list_custom_thresholds(self, **kwargs):
        return self.load_objects('custom_thresholds', **kwargs)

    # ----------------------------- Control físico -----------------------
    def open_door(self, portal_id: Any, *, duration: int = 5, **kwargs) -> Any:
        """Abre una puerta/portal durante `duration` segundos.

        Nota: depende del endpoint del dispositivo; se intenta `POST /portals/{id}/open`.
        """
        path = f"/{self.endpoint_map.get('portals','portals')}/{portal_id}/open"
        return self._post(path, json={'duration': duration}, **kwargs)

    def trigger_relay(self, secbox_id: Any, relay: int = 1, *, duration: int = 1, **kwargs) -> Any:
        path = f"/{self.endpoint_map.get('sec_boxs','sec-boxs')}/{secbox_id}/relay/{relay}/trigger"
        return self._post(path, json={'duration': duration}, **kwargs)

    # ----------------------------- Template sync ------------------------
    def template_sync_init(self, **kwargs) -> Any:
        """Inicia proceso de sincronización de plantillas (begin)."""
        return self._post('/templates/sync/init', **kwargs)

    def template_sync_end(self, **kwargs) -> Any:
        """Finaliza proceso de sincronización de plantillas (end)."""
        return self._post('/templates/sync/end', **kwargs)

    def message_to_screen(self, message: str, timeout: int = 3000, *, use_session_query: bool = False, session_param_name: str = 'session', **kwargs) -> Any:
        """Muestra un mensaje en la pantalla del equipo.

        Args:
            message: texto a mostrar en el equipo.
            timeout: milisegundos que dura el mensaje (ej. 3000).
            use_session_query: si True añade `?{session_param_name}=...` con el valor
                de la cookie de sesión (si el firmware requiere session en query).
            session_param_name: nombre del parámetro de sesión en la query (por defecto 'session').
            **kwargs: argumentos adicionales pasados a `_post`.

        Returns:
            Respuesta decodificada del dispositivo (JSON o texto).

        Nota: el endpoint típico usado por algunos firmwares es `/message_to_screen.fcgi`.
        Si tu dispositivo tiene un path distinto, pásalo directamente a `_post`.
        """
        payload = {'message': str(message), 'timeout': int(timeout)}
        path = '/message_to_screen.fcgi'
        if use_session_query:
            # intentar obtener nombre de cookie de sesión común si existe
            cookie_val = None
            # comprobar varias claves comunes
            for key in (session_param_name, 'session', 'PHPSESSID', 'sessionid'):
                v = self.session.cookies.get(key)
                if v:
                    cookie_val = v
                    break
            if cookie_val:
                path = f"{path}?{session_param_name}={cookie_val}"
        return self._post(path, json=payload, **kwargs)

    # ----------------------------- Scheduled unlocks --------------------
    def list_scheduled_unlocks(self, **kwargs):
        return self.load_objects('scheduled_unlocks', **kwargs)

    def create_scheduled_unlock(self, payload: Mapping[str, Any], **kwargs):
        self._validate_required(payload, ['portal_id', 'start_time', 'end_time'])
        return self.create_object('scheduled_unlocks', payload, **kwargs)

    # ----------------------------- Audit logs ---------------------------
    def get_change_logs(self, **kwargs):
        return self.load_objects('catra_infos', **kwargs)

    # ----------------------------- Helpers multi-device ----------------
    def switch_device(self, host: str, username: Optional[str] = None, password: Optional[str] = None, protocol: str = 'http', port: Optional[int] = None) -> None:
        """Cambia el cliente para apuntar a otro dispositivo.

        Guarda token si existe para poder alternar entre dispositivos.
        """
        # guardar token actual por host
        current_host = self.device.host
        if self.token and current_host:
            self.multi_device_tokens[current_host] = self.token
        # actualizar device info
        self.device = DeviceInfo(host=host, port=port, protocol=protocol)
        if username:
            self.username = username
        if password:
            self.password = password
        # restaurar token si existía
        token = self.multi_device_tokens.get(host)
        if token:
            self.token = token
            self.session.headers.update({'Authorization': f'Bearer {token}'})
        else:
            # limpiar token y cookies para el nuevo dispositivo
            self.token = None
            for h in ('Authorization',):
                self.session.headers.pop(h, None)
            self.session.cookies.clear()


if __name__ == '__main__':
    print('Este archivo implementa la clase ControlIDClient. Importarlo desde tu código.')
