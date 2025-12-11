from controlid_client import ControlIDClient

# Ajusta host/port/protocol si hace falta
client = ControlIDClient(host='192.168.1.100', username='admin', password='admin', protocol='http', cache_ttl=0)

# Intentar login e imprimir raw respuesta
try:
    resp = client.login()
    print('Login OK, response JSON:', resp)
except Exception as e:
    print('Login falló:', type(e).__name__, e)
    # Para depurar, hacer una llamada explícita con requests:
    import requests
    r = requests.post('http://192.168.1.100/login', json={'username':'admin','password':'admin'})
    print('Raw status:', r.status_code, 'headers:', r.headers)
    try:
        print('Raw json:', r.json())
    except Exception:
        print('Raw text:', r.text)
    raise

# Probar listar usuarios
try:
    users = client.list_users(page=1, per_page=20)
    print('Users:', users)
except Exception as e:
    print('list_users error:', type(e).__name__, e)

# Intentar abrir puerta  (ajusta portal_id)
try:
    res = client.open_door(portal_id=1, duration=3)
    print('open_door result:', res)
except Exception as e:
    print('open_door error:', type(e).__name__, e)