from controlid_client import ControlIDClient

HOST = '192.168.100.22'
USERNAME = 'Admin'
PASSWORD = 'your_password'

client = ControlIDClient(host=HOST, username=USERNAME, password=PASSWORD, protocol='http', port=80, timeout=10)
# login (requests.Session will store cookies automatically)
resp = client.login()
print('Login response:', resp)

# Inspect cookies (session cookie name depends on device firmware)
print('Cookies after login:', client.session.cookies.get_dict())

# Attendance payload
payload = {
    "general": {"attendance_mode": "1"},
    "identifier": {"log_type": "1"}
}

# POST to set_configuration.fcgi
result = client._post('/set_configuration.fcgi', json=payload)
print('set_configuration result:', result)