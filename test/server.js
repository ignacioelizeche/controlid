const express = require('express');
const bodyParser = require('body-parser');
const cors = require('cors');
const path = require('path');
const fs = require('fs');
const sqlite3 = require('sqlite3').verbose();
const axios = require('axios');

// control-id modules
const Login = require('control-id/login/Login');
const Users = require('control-id/users/User');
const System = require('control-id/system/System');
const Facial = require('control-id/facial_recognition/FacialRecognition');

const app = express();
app.use(cors());
app.use(bodyParser.json());

// Serve static UI
app.use(express.static(path.join(__dirname, 'public')));

// Simple whitelist of available commands and their params
const commands = {
  login: { desc: 'Login and return session', params: ['deviceIp','login','password'] },
  getUsers: { desc: 'Get users list', params: ['deviceIp','session'] },
  getUser: { desc: 'Get single user by id', params: ['deviceIp','session','user_id'] },
  getUserByRegistration: { desc: 'Get user by registration', params: ['deviceIp','session','registration'] },
  addUser: { desc: 'Add a user', params: ['deviceIp','session','name','registration','start','end','id'] },
  deleteUser: { desc: 'Delete user by id', params: ['deviceIp','session','user_id'] },
  updateUser: { desc: 'Update user', params: ['deviceIp','session','user_id','start','end'] },
  addGroup: { desc: 'Create user group association', params: ['deviceIp','session','user_id','group_id'] },
  getSystemInfo: { desc: 'Get system information', params: ['deviceIp','session'] },
  getAccessLogs: { desc: 'Get access logs', params: ['deviceIp','session','limit'] },
  fr_registerImage: { desc: 'Facial register image (base64)', params: ['deviceIp','session','match','user_id','image_base64'] },
  fr_getUserImage: { desc: 'Get face image by user id', params: ['deviceIp','session','user_id'] },
  setMonitorConfig: { desc: 'Set monitor configuration on device', params: ['deviceIp','session','monitor'] }
};

// Ensure data directory exists
const dataDir = path.join(__dirname, 'data');
if (!fs.existsSync(dataDir)) fs.mkdirSync(dataDir, { recursive: true });

// Initialize sqlite DB
const dbFile = path.join(dataDir, 'devices.db');
const db = new sqlite3.Database(dbFile);
db.serialize(() => {
  db.run(`CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    ip TEXT,
    login TEXT,
    password TEXT,
    defaults TEXT
  )`);
});

// register monitor endpoints (in separate module)
const { registerMonitor } = require('./monitor');
registerMonitor && registerMonitor(app, db);

// Devices CRUD
app.get('/api/devices', (req, res) => {
  db.all('SELECT * FROM devices', (err, rows) => {
    if (err) return res.status(500).json({ error: err.message });
    // parse defaults
    rows = rows.map(r => ({ ...r, defaults: r.defaults ? JSON.parse(r.defaults) : {} }));
    res.json(rows);
  });
});

// Session cache: stored in-memory with TTL
const sessionCache = new Map(); // deviceId -> { session, expiresAt }
const SESSION_TTL_MS = 5 * 60 * 1000; // 5 minutes

app.get('/api/sessions', (req, res) => {
  const out = {};
  for(const [k, v] of sessionCache.entries()){
    out[k] = { session: v.session, expiresAt: v.expiresAt };
  }
  res.json(out);
});

app.delete('/api/sessions/:deviceId', (req, res) => {
  const id = req.params.deviceId;
  const existed = sessionCache.delete(id);
  res.json({ deleted: existed });
});

app.get('/api/devices/:id', (req, res) => {
  const id = req.params.id;
  db.get('SELECT * FROM devices WHERE id = ?', [id], (err, row) => {
    if (err) return res.status(500).json({ error: err.message });
    if (!row) return res.status(404).json({ error: 'Not found' });
    row.defaults = row.defaults ? JSON.parse(row.defaults) : {};
    res.json(row);
  });
});

app.post('/api/devices', (req, res) => {
  const { name, ip: deviceIp, login: deviceLogin, password: devicePassword, defaults } = req.body;
  const defaultsStr = defaults ? JSON.stringify(defaults) : JSON.stringify({});
  db.run('INSERT INTO devices (name, ip, login, password, defaults) VALUES (?, ?, ?, ?, ?)', [name, deviceIp, deviceLogin, devicePassword, defaultsStr], function(err) {
    if (err) return res.status(500).json({ error: err.message });
    res.json({ id: this.lastID });
  });
});

app.put('/api/devices/:id', (req, res) => {
  const id = req.params.id;
  const { name, ip: deviceIp, login: deviceLogin, password: devicePassword, defaults } = req.body;
  const defaultsStr = defaults ? JSON.stringify(defaults) : JSON.stringify({});
  db.run('UPDATE devices SET name=?, ip=?, login=?, password=?, defaults=? WHERE id=?', [name, deviceIp, deviceLogin, devicePassword, defaultsStr, id], function(err) {
    if (err) return res.status(500).json({ error: err.message });
    res.json({ changed: this.changes });
  });
});

app.delete('/api/devices/:id', (req, res) => {
  const id = req.params.id;
  db.run('DELETE FROM devices WHERE id=?', [id], function(err) {
    if (err) return res.status(500).json({ error: err.message });
    res.json({ deleted: this.changes });
  });
});

app.get('/api/commands', (req, res) => {
  res.json(commands);
});

app.post('/api/execute', async (req, res) => {
  try {
    let { command, params } = req.body;
    if (!commands[command]) return res.status(400).json({ error: 'Unknown command' });

    // If params contains deviceId, fetch device and merge defaults
    if (params && params.deviceId) {
      const deviceId = params.deviceId;
      // synchronous wrapper for sqlite get
      params = { ...params };
      const device = await new Promise((resolve, reject) => {
        db.get('SELECT * FROM devices WHERE id = ?', [deviceId], (err, row) => {
          if (err) return reject(err);
          if (!row) return resolve(null);
          row.defaults = row.defaults ? JSON.parse(row.defaults) : {};
          resolve(row);
        });
      });
      if (device) {
        // fill missing params from device
        params.deviceIp = params.deviceIp || device.ip;
        params.login = params.login || device.login;
        params.password = params.password || device.password;
        // merge any command-specific defaults
        if (device.defaults) {
          params = { ...device.defaults[command], ...params };
        }
      }
    }

    // If params contains deviceId, try to use cached session first
    if (params && params.deviceId) {
      const cached = sessionCache.get(String(params.deviceId));
      if (cached && cached.expiresAt > Date.now()) {
        params.session = params.session || cached.session;
      }
    }

    // If no session provided but login/password available, perform login automatically for convenience
    if (params && !params.session && params.deviceIp && params.login && params.password) {
      try {
        // Attempt cached session by deviceIp? (cache keyed by deviceId only)
        const lg = new Login(params.deviceIp, params.login, params.password);
        const session = await lg.login();
        params.session = session;
        // store in cache if deviceId provided
        if (params.deviceId) {
          sessionCache.set(String(params.deviceId), { session, expiresAt: Date.now() + SESSION_TTL_MS });
        }
      } catch (e) {
        // ignore login failure here; later calls will fail with clear error
        console.warn('Auto-login failed:', e.message || e);
      }
    }

    let result;
    if (command === 'login') {
      const { deviceIp, login='admin', password='admin' } = params || {};
      const lg = new Login(deviceIp, login, password);
      const session = await lg.login();
      result = { session };
    } else if (command === 'getUsers') {
      const { deviceIp, session } = params || {};
      const users = new Users(deviceIp, session);
      result = await users.getUsers();
    } else if (command === 'addUser') {
      const { deviceIp, session, name, registration, start, end, id } = params || {};
      const users = new Users(deviceIp, session);
      result = await users.addUser(name, registration, start, end, id);
    } else if (command === 'getSystemInfo') {
      const { deviceIp, session } = params || {};
      const sys = new System(deviceIp, session);
      result = await sys.getSystemInfo();
    } else if (command === 'getAccessLogs') {
      // Build and POST a request that uses `fields` as an array (device expects array, not object).
      // If deviceIp/session aren't present, try to resolve from deviceId (merged earlier if provided).
      let { deviceIp, session, limit } = params || {};

      // if deviceId provided but deviceIp missing, fetch device record
      if ((!deviceIp || !session) && params && params.deviceId) {
        const device = await new Promise((resolve, reject) => {
          db.get('SELECT * FROM devices WHERE id = ?', [params.deviceId], (err, row) => {
            if (err) return reject(err);
            resolve(row ? { ...row, defaults: row.defaults ? JSON.parse(row.defaults) : {} } : null);
          });
        });
        if (device) {
          deviceIp = deviceIp || device.ip;
          // session may already be in params due to auto-login earlier
        }
      }

      if (!deviceIp) {
        // fallback to using wrapper which will give a clearer error
        const sys = new System(deviceIp, session);
        result = await sys.getAccessLogs();
      } else {
        // common fields to request from access_logs; device expects an array here
        const fieldsArray = ['id','user_id','registration','time','event','device_id','door_id','access_event_id'];
        const body = { object: 'access_logs', fields: fieldsArray };
        if (limit) {
          const n = parseInt(limit, 10);
          if (!Number.isNaN(n) && n > 0) body.limit = n;
        }

        // try the common endpoints used by devices; prefer get_access_logs.fcgi, then load_objects
        const attempts = [
          `/get_access_logs.fcgi`,
          `/get_access_logs`,
          `/load_objects`,
        ];

        let responded = false;
        for (const p of attempts) {
          try {
            const url = `http://${deviceIp}${p}?session=${session || ''}`;
            console.log('getAccessLogs POST ->', url, 'body=', JSON.stringify(body));
            const r = await axios.post(url, body, { headers: { 'Content-Type': 'application/json' }, timeout: 15000 });
            result = r.data;
            responded = true;
            break;
          } catch (err) {
            // try next
            // record last error for fallback
            const respData = err.response && err.response.data ? err.response.data : null;
            console.warn('getAccessLogs attempt failed for', p, 'err=', err.message || err, 'response=', respData);
            result = respData || null;
          }
        }

        if (!responded) {
          // final fallback: try the System wrapper which may build a different request
          const sys = new System(deviceIp, session);
          result = await sys.getAccessLogs();
        }
      }
    } else if (command === 'setMonitorConfig') {
      // Accept either deviceIp+session or deviceId (will be merged earlier in flow)
      let { deviceIp, session, monitor } = params || {};
      // If deviceId was provided but deviceIp not present, try to fetch device
      if ((!deviceIp || !session) && params && params.deviceId) {
        const device = await new Promise((resolve, reject) => {
          db.get('SELECT * FROM devices WHERE id = ?', [params.deviceId], (err, row) => {
            if (err) return reject(err);
            resolve(row ? { ...row, defaults: row.defaults ? JSON.parse(row.defaults) : {} } : null);
          });
        });
        if (device) {
          deviceIp = deviceIp || device.ip;
          // if session missing, auto-login was attempted earlier; session may now be in params.session
        }
      }

      if (!deviceIp) return res.status(400).json({ error: 'deviceIp (or deviceId) is required' });
      if (!monitor || typeof monitor !== 'object') return res.status(400).json({ error: 'monitor object required' });

      // Normalize monitor object: ensure types and clean path
      function normalizeMonitor(m){
        const out = {};
        if (m.request_timeout !== undefined) out.request_timeout = String(m.request_timeout);
        if (m.hostname !== undefined) out.hostname = String(m.hostname);
        if (m.port !== undefined) out.port = String(m.port);
        if (m.path !== undefined) {
          // ensure exactly one leading slash, no trailing slash
          const cleaned = String(m.path).replace(/^\/+|\/+$/g, '');
          out.path = cleaned ? `/${cleaned}` : '';
        }
        if (m.alive_interval !== undefined) out.alive_interval = String(m.alive_interval);
        if (m.enable_photo_upload !== undefined) out.enable_photo_upload = (m.enable_photo_upload === true || m.enable_photo_upload === '1' || m.enable_photo_upload === 1) ? '1' : '0';
        if (m.inform_access_event_id !== undefined) out.inform_access_event_id = String(m.inform_access_event_id);
        // copy any other keys as-is
        Object.keys(m).forEach(k => {
          if (!out.hasOwnProperty(k)) out[k] = m[k];
        });
        return out;
      }

      const monitorPayload = normalizeMonitor(monitor);

      // post to device /set_configuration.fcgi?session=
      try {
        const url = `http://${deviceIp}/set_configuration.fcgi?session=${session || ''}`;
        const response = await axios.post(url, { monitor: monitorPayload }, { headers: { 'Content-Type': 'application/json' }, timeout: 15000 });
        result = response.data;
      } catch (err) {
        const detail = err.response && err.response.data ? err.response.data : null;
        console.error('Error setting monitor config:', err.message || err, 'payload:', monitorPayload, 'response:', detail);
        return res.status(500).json({ error: err.message || String(err), detail });
      }
    } else {
      return res.status(400).json({ error: 'Not implemented' });
    }

    res.json({ success: true, result });
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: e.message || String(e) });
  }
});

// Fetch full device configuration (get_configuration) and extract monitor module params
app.get('/api/devices/:id/configuration', async (req, res) => {
  try {
    const id = req.params.id;
    const device = await new Promise((resolve, reject) => {
      db.get('SELECT * FROM devices WHERE id = ?', [id], (err, row) => {
        if (err) return reject(err);
        resolve(row ? { ...row, defaults: row.defaults ? JSON.parse(row.defaults) : {} } : null);
      });
    });
    if (!device) return res.status(404).json({ error: 'Device not found' });
    if (!device.ip) return res.status(400).json({ error: 'Device has no IP configured' });

    // try cached session
    let session;
    const cached = sessionCache.get(String(id));
    if (cached && cached.expiresAt > Date.now()) session = cached.session;

    // if no session, try login using saved credentials
    if (!session) {
      if (!device.login || !device.password) return res.status(400).json({ error: 'No cached session and device has no credentials stored' });
      try {
        const lg = new Login(device.ip, device.login, device.password);
        session = await lg.login();
        sessionCache.set(String(id), { session, expiresAt: Date.now() + SESSION_TTL_MS });
      } catch (e) {
        return res.status(500).json({ error: 'Auto-login failed', detail: e.message || String(e) });
      }
    }

    // request configuration from device
    try {
      const url = `http://${device.ip}/get_configuration.fcgi?session=${session || ''}`;
      // force text response so we get raw XML even if Content-Type confuses axios
      const response = await axios.get(url, { timeout: 15000, responseType: 'text' });
      // response should now be raw text (XML)
      const text = String(response.data || '');
      const status = response.status;
      const contentType = response.headers && response.headers['content-type'];

      // try to extract <module name="monitor"> ... </module>
      const moduleMatch = text.match(/<module[^>]*name=["']monitor["'][^>]*>([\s\S]*?)<\/module>/i);
      const monitorModule = moduleMatch ? moduleMatch[1] : null;
      const params = [];
      if (monitorModule) {
        const re = /<param[^>]*name=["']([^"']+)["'][^>]*>/g;
        let m;
        while ((m = re.exec(monitorModule)) !== null) {
          params.push(m[1]);
        }
      }

      return res.json({ monitorModuleExists: !!monitorModule, params, raw: text.substring(0, 200000), status, contentType });
    } catch (err) {
      const detail = err.response && err.response.data ? err.response.data : err.message || String(err);
      return res.status(500).json({ error: 'Failed to fetch configuration', detail });
    }
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: e.message || String(e) });
  }
});

// Fetch many endpoints from device to show full available configuration and responses
app.get('/api/devices/:id/fullconfig', async (req, res) => {
  try {
    const id = req.params.id;
    const device = await new Promise((resolve, reject) => {
      db.get('SELECT * FROM devices WHERE id = ?', [id], (err, row) => {
        if (err) return reject(err);
        resolve(row ? { ...row, defaults: row.defaults ? JSON.parse(row.defaults) : {} } : null);
      });
    });
    if (!device) return res.status(404).json({ error: 'Device not found' });
    if (!device.ip) return res.status(400).json({ error: 'Device has no IP configured' });

    // ensure session (reuse code from configuration endpoint)
    let session;
    const cached = sessionCache.get(String(id));
    if (cached && cached.expiresAt > Date.now()) session = cached.session;
    if (!session) {
      if (!device.login || !device.password) return res.status(400).json({ error: 'No cached session and device has no credentials stored' });
      try {
        const lg = new Login(device.ip, device.login, device.password);
        session = await lg.login();
        sessionCache.set(String(id), { session, expiresAt: Date.now() + SESSION_TTL_MS });
      } catch (e) {
        return res.status(500).json({ error: 'Auto-login failed', detail: e.message || String(e) });
      }
    }

    const candidatePaths = [
      '/get_configuration.fcgi',
      '/get_modules.fcgi',
      '/get_system_info.fcgi',
      '/get_configuration.cgi',
      '/get_monitor.fcgi',
      '/get_all_config.fcgi',
      '/get_configuration_xml.fcgi'
    ];

    const results = {};
    for (const p of candidatePaths) {
      const url = `http://${device.ip}${p}?session=${session || ''}`;
      try {
        const r = await axios.get(url, { timeout: 15000, responseType: 'text' });
        results[p] = { status: r.status, contentType: r.headers && r.headers['content-type'], body: String(r.data).substring(0, 200000) };
      } catch (err) {
        const detail = err.response && err.response.data ? String(err.response.data).substring(0,200000) : (err.message || String(err));
        results[p] = { error: true, detail };
      }
    }

    // Also include system info using wrapper (if available)
    let systemInfo = null;
    try {
      const sys = new System(device.ip, session);
      systemInfo = await sys.getSystemInfo();
    } catch (e) {
      systemInfo = { error: e.message || String(e) };
    }

    return res.json({ deviceId: id, ip: device.ip, session: !!session, systemInfo, endpoints: results });
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: e.message || String(e) });
  }
});

// Proxy to POST /get_configuration.fcgi on the device. Accepts optional JSON body to request specific sections.
app.post('/api/devices/:id/getconfig', async (req, res) => {
  try {
    const id = req.params.id;
    const body = req.body && Object.keys(req.body).length ? req.body : {};
    const device = await new Promise((resolve, reject) => {
      db.get('SELECT * FROM devices WHERE id = ?', [id], (err, row) => {
        if (err) return reject(err);
        resolve(row ? { ...row, defaults: row.defaults ? JSON.parse(row.defaults) : {} } : null);
      });
    });
    if (!device) return res.status(404).json({ error: 'Device not found' });
    if (!device.ip) return res.status(400).json({ error: 'Device has no IP configured' });

    // ensure session
    let session;
    const cached = sessionCache.get(String(id));
    if (cached && cached.expiresAt > Date.now()) session = cached.session;
    if (!session) {
      if (!device.login || !device.password) return res.status(400).json({ error: 'No cached session and device has no credentials stored' });
      try {
        const lg = new Login(device.ip, device.login, device.password);
        session = await lg.login();
        sessionCache.set(String(id), { session, expiresAt: Date.now() + SESSION_TTL_MS });
      } catch (e) {
        return res.status(500).json({ error: 'Auto-login failed', detail: e.message || String(e) });
      }
    }

    const url = `http://${device.ip}/get_configuration.fcgi?session=${session || ''}`;
    try {
      const r = await axios.post(url, body, { headers: { 'Content-Type': 'application/json' }, timeout: 20000 });
      // return whatever the device returned
      return res.status(200).json({ status: r.status, contentType: r.headers && r.headers['content-type'], body: r.data });
    } catch (err) {
      const detail = err.response && err.response.data ? err.response.data : err.message || String(err);
      return res.status(500).json({ error: 'Failed to POST get_configuration', detail });
    }
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: e.message || String(e) });
  }
});

// Return the monitor webhook URL and an example monitor config
app.get('/api/monitor/url/:deviceId?', (req, res) => {
  const host = req.get('host');
  const protocol = req.protocol;
  const base = `${protocol}://${host}`;
  const deviceId = req.params.deviceId || null;

  // Provide the base notification path and an example monitor configuration
  const notificationBase = `${base}/api/notifications`;
  const paths = {
    dao: `${notificationBase}/dao`,
    usb_drive: `${notificationBase}/usb_drive`,
    template: `${notificationBase}/template`,
    user_image: `${notificationBase}/user_image`,
    card: `${notificationBase}/card`,
    pin: `${notificationBase}/pin`,
    password: `${notificationBase}/password`,
    catra_event: `${notificationBase}/catra_event`,
    operation_mode: `${notificationBase}/operation_mode`,
    device_is_alive: `${notificationBase}/device_is_alive`,
    door: `${notificationBase}/door`,
    secbox: `${notificationBase}/secbox`,
    access_photo: `${notificationBase}/access_photo`
  };

  const exampleMonitor = {
    hostname: req.hostname || host,
    port: (req.socket && req.socket.localPort) || process.env.PORT || 3000,
    path: '/api/notifications',
    alive_interval: 60,
    enable_photo_upload: true,
    inform_access_event_id: 1,
    // the device will POST JSON objects to e.g. `${hostname}:${port}${path}/dao`
    note: 'Use the appropriate path above for each notification type. If using a local dev server, expose the port with a public tunnel (ngrok) for devices on another network.'
  };

  res.json({ base, paths, exampleMonitor, deviceId });
});

// Self-test endpoint: post sample monitor events to local endpoints and return DB-stored events
app.get('/api/monitor/selftest', async (req, res) => {
  try {
    const serverPort = process.env.PORT || 3000;
    const base = `http://localhost:${serverPort}`;
    const samples = [
      { path: 'dao', body: { object_changes: [{ object: 'access_logs', type: 'inserted', values: { id: '999', time: Math.floor(Date.now()/1000).toString(), event: '12', device_id: '123', user_id: '0' } }], device_id: 123 } },
      { path: 'usb_drive', body: { usb_drive: { event: 'Export formatted access logs routine succeeded' }, device_id: 123, time: Math.floor(Date.now()/1000) } },
      { path: 'template', body: { template: { id: 't1' }, device_id: 123 } },
      { path: 'user_image', body: { user_image: { id: 'u1' }, device_id: 123 } },
      { path: 'card', body: { card: { id: 'c1' }, device_id: 123 } },
      { path: 'pin', body: { pin: { id: 'p1' }, device_id: 123 } },
      { path: 'password', body: { password: { id: 'pw1' }, device_id: 123 } },
      { path: 'catra_event', body: { event: { type: 7, name: 'TURN LEFT', time: Math.floor(Date.now()/1000), uuid: '0e039178' }, access_event_id: 15, device_id: 123, time: Math.floor(Date.now()/1000) } },
      { path: 'operation_mode', body: { operation_mode: { mode: 0, mode_name: 'DEFAULT', time: Math.floor(Date.now()/1000), last_offline: 0, exception_mode: 'none' }, device_id: 123 } },
      { path: 'device_is_alive', body: { access_logs: 0, device_id: 123, time: Math.floor(Date.now()/1000) } },
      { path: 'door', body: { door: { id: 1, open: true }, access_event_id: 15, device_id: 123, time: Math.floor(Date.now()/1000) } },
      { path: 'secbox', body: { secbox: { id: 122641794705028910, open: true }, access_event_id: 15 } },
      { path: 'access_photo', body: { device_id: '123', time: Math.floor(Date.now()/1000), portal_id: '1', identifier_id: '0', event: '7', user_id: '0', access_photo: '' } }
    ];

    const results = [];
    for (const s of samples) {
      const url = `${base}/api/notifications/${s.path}`;
      try {
        const r = await axios.post(url, s.body, { headers: { 'Content-Type': 'application/json' }, timeout: 5000 });
        results.push({ path: s.path, status: r.status, ok: true });
      } catch (err) {
        const detail = err.response && err.response.data ? err.response.data : err.message || String(err);
        results.push({ path: s.path, status: err.response ? err.response.status : null, ok: false, detail });
      }
    }

    // read last events from monitor_events table if exists
    const events = await new Promise((resolve) => {
      db.all("SELECT id, path, device_id, created_at, payload FROM monitor_events ORDER BY id DESC LIMIT 50", (err, rows) => {
        if (err) return resolve({ error: String(err) });
        resolve(rows);
      });
    });

    res.json({ posted: results, storedEvents: events });
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: e.message || String(e) });
  }
});

const port = process.env.PORT || 3000;
app.listen(port, () => console.log(`Server listening on http://localhost:${port}`));
