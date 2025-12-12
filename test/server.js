const express = require('express');
const bodyParser = require('body-parser');
const cors = require('cors');
const path = require('path');

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
  addUser: { desc: 'Add a user', params: ['deviceIp','session','name','registration','start','end','id'] },
  getSystemInfo: { desc: 'Get system information', params: ['deviceIp','session'] },
  getAccessLogs: { desc: 'Get access logs', params: ['deviceIp','session'] }
};

app.get('/api/commands', (req, res) => {
  res.json(commands);
});

app.post('/api/execute', async (req, res) => {
  try {
    const { command, params } = req.body;
    if (!commands[command]) return res.status(400).json({ error: 'Unknown command' });

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
