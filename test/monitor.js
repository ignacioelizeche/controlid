/*
  monitor.js
  Provide monitor endpoints and documentation export for the Test server.
  - registerMonitor(app, db): creates `monitor_events` table, registers POST endpoints
    under `/api/notifications/*` that persist received JSON payloads and reply {received:true}
  - GET /api/monitor-doc returns the monitor documentation (plain text)
 */

const MONITOR_DOC = `
Introduction to Monitor

Whether in Standalone mode or Pro or Enterprise mode, to monitor asynchronous events you will need to use the services provided by the Monitor.

As the name suggests, the monitor allows the monitoring of events that occur in the device. It sends them to an external server that must be configured through the endpoints described below.

To use the monitor you need to set some configuration parameters described in monitor.

Request example
This request will configure the monitor.

$.ajax({
        url: "/set_configuration.fcgi?session=" + session,
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(
            {
                "monitor": {
                      "request_timeout": "5000",
                      "hostname": "192.168.0.20",
                      "port": "8000",
                      "path": "api/notifications" //standard path 
                  }
            }
        )
    });

Note: The hostname parameter in the configuration example above can also be a domain address, such as myserver.com, in addition to an IP address.

Endpoints
An endpoint of a web server is the URL by which one of its services can be accessed by a client application. Therefore, endpoints are interfaces between the API and the application.

In the case of the monitor, the access control terminal takes on the role of the client application and it is needed to establish an external server that implements the endpoints wanted to consume.

The final URL to which the events will be sent by the device will be:

hostname:port/endpoint
Endpoints examples:

http://myserver.com/api/notifications/dao
192.168.110.200:80/api/notifications/dao

Logs
POST /api/notifications/dao
Sent when changes occur in the access_logs, alarm_logs, cards, and templates tables. These changes can include, insertions, updates, and deletions.

JSON format that the device sends to the server:

{
  "object_changes": [
    {
      "object": "access_logs",
      "type": "inserted",
      "values": {
        "id": "519",
        "time": "1532977090",
        "event": "12",
        "device_id": "478435",
        "identifier_id": "0",
        "user_id": "0",
        "portal_id": "1",
        "identification_rule_id": "0",
        "card_value": "0",
        "log_type_id": "-1"
      }
    }
  ],
  "device_id": 478435
}
POST /api/notifications/usb_drive
Sent when there is an usb_drive audit log inclusion. See Export Report for more information.

JSON format that the device sends to the server:

{
  "usb_drive": {
    "event":"Export formatted access logs routine succeeded [uuid=2C9D-476B]"
  },
  "device_id": 478435,
  "time" : 1490271121
}
Remote enrollment
POST /api/notifications/template
Sent when a template is enrolled remotely, if the sync and save parameters of the request to the /remote_enroll.fcgi endpoint are false. See Remote Enrollment - Fingerprint, Face, Card, PIN or Password for more information.

POST /api/notifications/user_image
Sent when a face is enrolled remotely, if the sync and save parameters of the request to the /remote_enroll.fcgi endpoint are false. See Remote Enrollment - Fingerprint, Face, Card, PIN or Password for more information.

POST /api/notifications/card
Sent when a card is enrolled remotely, if the sync and save parameters of the request to the /remote_enroll.fcgi endpoint are false. See Remote Enrollment - Fingerprint, Face, Card, PIN or Password for more information.

POST /api/notifications/pin
Sent when a PIN is enrolled remotely, if the sync and save parameters of the request to the /remote_enroll.fcgi endpoint are false. See Remote Enrollment - Fingerprint, Face, Card, PIN or Password for more information.

POST /api/notifications/password
Sent when a password is enrolled remotely, if the sync and save parameters of the request to the /remote_enroll.fcgi endpoint are false. See Remote Enrollment - Fingerprint, Face, Card, PIN or Password for more information.

Turnstile events
POST /api/notifications/catra_event
This endpoint is exclusive to the iDBlock turnstile and sends turning confirmation events. Possible events are:

EVENT_TURN_LEFT: Left-turn confirmation, which can be entrance or exit depending on the value of gateway parameter.
EVENT_TURN_RIGHT: Right-turn confirmation, which can be entrance or exit depending on the value of gateway parameter.
EVENT_GIVE_UP: Occurs when a user identifies himself at the turnstile and has his access authorized, but does not pass through it, thus giving up on performing the access/turning.
JSON format that the device sends to the server:

{
  "event": {
    "type": 7,
    "name": 'TURN LEFT',
    "time": 1484126902,
    "uuid": "0e039178"
  },
  "access_event_id": 15,
  "device_id": 935107,
  "time": 1484126902
}
Comments:

This JSON format has an optional field access_event_id which links the event to the correspondent id from the table access_events. This field is included when the monitor configuration parameter inform_access_event_id is set to 1.
Online state
POST /api/notifications/operation_mode
A request is sent when there is a change in the device's operation mode (e.g.: enters or leaves contingency mode). When the device turns on, this request is sent with the field "last_offline": 0. There is also the field exception_mode that indicates if the device is in exception mode (it can be empty).

JSON format that the device sends to the server:

{
  "operation_mode": {
    "mode": 0,
    "mode_name": "DEFAULT",
    "time": 1490271121,
    "last_offline": 1490261121
    "exception_mode": "none"
  },
  "device_id": 123456
}
POST /api/notifications/device_is_alive
A request is sent to monitor the device connection when standalone mode is enabled. The interval between requests is determined by the alive_interval setting, which is 30 seconds by default. This setting, given in milliseconds, can be modified through the set_configuration endpoint and obtained through the get_configuration endpoint, both with the following parameters:

'set_configuration'
{
  monitor: {
    alive_interval: 30000
  }
}
And

'get_configuration'
{
  monitor: [alive_interval]
}
The request body (in JSON format) contains the number of available logs.

JSON format that the device sends to the server:

{
  "access_logs": 0,
  "device_id": 6613047045004349,
  "time": 1739376235
}
Actions
POST /api/notifications/door
A request is sent at this endpoint when a door state change occurs, which in most cases will indicate when a door is opened or closed. This change is perceived by the equipment in two different ways:

Relay opening or closing.
Change of the door sensor reading (only if the corresponding sensor is active: see door_sensorN_enabled)
The request contains the id of the door that changed state and its current state (open or closed). The door ID is represented by an integer that goes from 1 to the number of available doors, up to 4 if it is an iDBox device. The state of the door is a boolean parameter open: true if it is open and false if it is closed.

The state reported in the open parameter can be the state read from the door sensor, if the door sensor is active, or the state of the relay, otherwise.

JSON format that the device sends to the server:

{
  "door": {
    "id" : 1,
    "open" : true
  },
  "access_event_id": 15,
  "device_id": 1038508,
  "time": 1575475894
}
Comments:

This JSON format has an optional field access_event_id which links the event to the correspondent id from the table access_events. This field is included when the monitor configuration parameter inform_access_event_id is set to 1.
POST /api/notifications/secbox
A request is sent at this endpoint when the relay in the security box changes state, which will indicate when a door is opened or closed.

The request contains the ID of the door that changed its state and its current state. The door ID is represented by an integer while the state is a boolean value, which is true if it is open and false if it is closed.

JSON format that the device sends to the server:

{
  "secbox": {
    "id" : 122641794705028910,
    "open" : true
  },
  "access_event_id": 15
}
Comments:

This JSON format has an optional field access_event_id which links the event to the correspondent id from the table access_events. This field is included when the monitor configuration parameter inform_access_event_id is set to 1.
POST /api/notifications/access_photo
A request is sent at this endpoint when there is some kind of identification event and the option to send images via monitor is enabled. This option can be found on both the device interface and the WEB interface, and can be modified through the set_configuration endpoint, and obtained through the get_configuration endpoint, both using the following parameters:

'set_configuration'
{
  monitor: {
    enable_photo_upload: true
  }
}
And

'get_configuration'
{
  monitor: [enable_photo_upload]
}
The request contains the id of the port triggered by the identification, the ID of the device that performed the identification, the time at which the identification took place, the ID of the identified user, as well as a photo taken by the device at the time of identification.

JSON format that the device sends to the server:

{
  "device_id": "478435",
  "time": "1532977090",
  "portal_id": "1",
  "identifier_id": "0",
  "event": "7",
  "user_id": "0",
  "access_photo" : photo in jpeg format, encoded in base64.
}
Note: - The photo sent will be in jpeg format, encoded in base64.
`;

function registerMonitor(app, db){
  // Ensure monitor_events table
  db.serialize(() => {
    db.run(`CREATE TABLE IF NOT EXISTS monitor_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      endpoint TEXT,
      payload TEXT,
      received_at INTEGER
    )`);
  });

  const endpoints = [
    'dao','usb_drive','template','user_image','card','pin','password',
    'catra_event','operation_mode','device_is_alive','door','secbox','access_photo'
  ];

  endpoints.forEach(ep => {
    const path = `/api/notifications/${ep}`;
    app.post(path, (req, res) => {
      try {
        const payload = req.body || {};
        const now = Math.floor(Date.now()/1000);
        db.run('INSERT INTO monitor_events (endpoint, payload, received_at) VALUES (?,?,?)', [ep, JSON.stringify(payload), now]);
        console.log('[monitor] received', path, JSON.stringify(payload));
        res.json({ received: true });
      } catch(e){
        console.error('[monitor] error', e);
        res.status(500).json({ error: String(e) });
      }
    });
  });

  // list events
  app.get('/api/monitor/events', (req,res)=>{
    db.all('SELECT * FROM monitor_events ORDER BY received_at DESC LIMIT 200', (err, rows)=>{
      if(err) return res.status(500).json({ error: err.message });
      rows = rows.map(r=> ({ ...r, payload: JSON.parse(r.payload) }));
      res.json(rows);
    });
  });

  // monitor documentation
  app.get('/api/monitor-doc', (req,res)=>{
    res.type('text').send(MONITOR_DOC);
  });
}

module.exports = { registerMonitor };
