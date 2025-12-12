# Test tools for ControlID Monitor integration

This folder contains helper scripts to validate the Monitor integration between ControlID devices and this repo's server.

Files
- `monitor_test.py`: configures the device monitor (via local server API) and polls `/api/monitor/events` waiting for a `device_is_alive` event.
- `smoke_push.py`: quick smoke tests (getSystemInfo/getconfig/setMonitorConfig) using the server API.
- `.env.example`: example environment file. Copy to `.env` and edit values.
- `run_test.sh`: convenience script to create a virtualenv, install deps and run the tests.

Requirements
- Python 3.8+
- `requests`, `python-dotenv` (the run script installs them)

Usage
1. Copy the example env and edit values:

```bash
cd Test
cp .env.example .env
# edit .env to point to your server and device
```

2. Start the local server (the repo `Test/server.js`):

```bash
# in project root
node server.js
```

3. Run the tests:

```bash
cd Test
./run_test.sh
```

What they do
- `smoke_push.py` attempts to contact the device (via the local server proxy), reads configuration and sets the monitor config.
- `monitor_test.py` sets the monitor and polls the server event store for a `device_is_alive` event.

If you prefer to manually run the scripts:

```bash
python smoke_push.py
python monitor_test.py
```

Notes
- The scripts call the local server's API endpoints (`/api/execute`, `/api/devices/:id/getconfig`, `/api/monitor/events`). Ensure the server is running and accessible.
- If your server is not `localhost:3000`, set `SERVER_HOST` and `SERVER_PORT` in `.env`.
- For debugging, run the scripts with `PYTHONVERBOSE=1` or inspect server logs.

If you want, I can also:
- Add these scripts to the main `package.json` scripts.
- Add a PowerShell runner for Windows.
- Create the diagram of the flow (Mermaid) and include it in the README.
