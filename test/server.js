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
      const { deviceIp, session } = params || {};
      const sys = new System(deviceIp, session);
      result = await sys.getAccessLogs();
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
          // remove leading/trailing slashes
          out.path = String(m.path).replace(/^\/+|\/+$/g, '');
        }
        if (m.alive_interval !== undefined) out.alive_interval = Number(m.alive_interval);
        if (m.enable_photo_upload !== undefined) out.enable_photo_upload = (m.enable_photo_upload === true || m.enable_photo_upload === '1' || m.enable_photo_upload === 1);
        if (m.inform_access_event_id !== undefined) out.inform_access_event_id = Number(m.inform_access_event_id);
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
        console.error('Error setting monitor config:', err.message || err, 'payload:', monitorPayload);
        return res.status(500).json({ error: err.message || String(err) });
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

const port = process.env.PORT || 3000;
app.listen(port, () => console.log(`Server listening on http://localhost:${port}`));
