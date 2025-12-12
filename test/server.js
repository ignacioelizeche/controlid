const express = require('express');
const bodyParser = require('body-parser');
const cors = require('cors');
const path = require('path');
const fs = require('fs');
const sqlite3 = require('sqlite3').verbose();

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
  fr_getUserImage: { desc: 'Get face image by user id', params: ['deviceIp','session','user_id'] }
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
    } else {
      return res.status(400).json({ error: 'Not implemented' });
    }

    res.json({ success: true, result });
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: e.message || String(e) });
  }
});

const port = process.env.PORT || 3000;
app.listen(port, () => console.log(`Server listening on http://localhost:${port}`));
