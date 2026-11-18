import os
import asyncio
import json
import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import paho.mqtt.client as mqtt

# ============================================================
# LOGGING
# ============================================================
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("rtm-backend")

# ============================================================
# MQTT CONFIG
# ============================================================
MQTT_HOST = os.getenv("MQTT_HOST", "192.168.1.66")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "benderang")
MQTT_PASS = os.getenv("MQTT_PASS", "benderangmqtt")

TOPIC_SONOFF = "/sonoff_benderang"
TOPIC_DISPENSER = "/iotdispenser_output"

# ============================================================
# GLOBAL STORAGE (CACHE DATA TERBARU DARI MQTT)
# ============================================================
latest_powermeter = {
    "event": "sonoff_data",
    "devices": []
}

latest_dispenser = {
    "suhuDingin": 0.0,
    "suhuPanas": 0.0,
    "autopump": 0,
    "ctrlPump": 0,
    "sw_heat_state": 0,
    "autocool": 0,
    "autohot": 0,
    "sw_door_state": 0,
    "float_sw_state": 0,
    "sw_cool_state": 0,
    "ctrlCompHot": 0,
    "ctrlCompCold": 0,
    "setpoint_cool": 0.0,
    "setpoint_heat": 0.0
}

# ============================================================
# MQTT CLIENT SETUP
# ============================================================
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="rtm-dashboard-backend")

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        log.info(f"MQTT Connected successfully to {MQTT_HOST}:{MQTT_PORT}")
        client.subscribe([(TOPIC_SONOFF, 0), (TOPIC_DISPENSER, 0)])
        log.info(f"Subscribed to topics: {TOPIC_SONOFF}, {TOPIC_DISPENSER}")
    else:
        log.error(f"MQTT Connection failed with code {reason_code}")

def on_message(client, userdata, msg):
    global latest_powermeter, latest_dispenser
    try:
        payload_str = msg.payload.decode("utf-8")
        data = json.loads(payload_str)

        if msg.topic == TOPIC_SONOFF:
            latest_powermeter = data
            log.info("Received data for Powermeter (/sonoff_benderang)")
        elif msg.topic == TOPIC_DISPENSER:
            latest_dispenser = data
            log.info("Received data for IoT Dispenser (/iotdispenser_output)")

    except Exception as e:
        log.error(f"Error parsing MQTT message on topic {msg.topic}: {e}")

mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

if MQTT_USER:
    mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)

# ============================================================
# FASTAPI APP & LIFESPAN
# ============================================================
app = FastAPI(title="RTM Monitoring System - Benderang")

@app.on_event("startup")
def startup_event():
    try:
        mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
        mqtt_client.loop_start()
        log.info("MQTT background loop started.")
    except Exception as e:
        log.error(f"Failed to connect to MQTT broker: {e}")

@app.on_event("shutdown")
def shutdown_event():
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
    log.info("MQTT client disconnected.")

# ============================================================
# REST API ENDPOINTS
# ============================================================
@app.get("/api/powermeter")
def get_powermeter():
    return latest_powermeter

@app.get("/api/dispenser")
def get_dispenser():
    return latest_dispenser


# ============================================================
# FRONTEND HTML / UI (PRESSMON THEME)
# ============================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RTM Monitor — Industrial Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Barlow+Condensed:wght@300;400;600;700;900&family=Barlow:wght@300;400;500&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #060a0f;
  --panel: #0b1118;
  --panel2: #0f1820;
  --border: #1a2a3a;
  --accent: #00d4ff;
  --accent2: #00ff9d;
  --text: #c8dce8;
  --text2: #5a7a8a;
  --green: #00ff9d;
  --yellow: #ffb800;
  --red: #ff3d3d;
  --blue: #00d4ff;
}
* { margin:0; padding:0; box-sizing:border-box; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: 'Barlow', sans-serif;
  font-size: 13px;
  min-height: 100vh;
}
/* SCANLINE EFFECT */
body::before {
  content:''; position:fixed; top:0; left:0; right:0; bottom:0;
  background: repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,212,255,0.01) 2px, rgba(0,212,255,0.01) 4px);
  pointer-events:none; z-index:9999;
}
.topbar {
  display:flex; align-items:center; justify-content:space-between;
  padding: 12px 20px; background: var(--panel); border-bottom: 1px solid var(--border);
  position:sticky; top:0; z-index:100;
}
.logo { display:flex; align-items:center; gap:12px; }
.logo-icon {
  width:36px; height:36px; background: linear-gradient(135deg, var(--accent), var(--accent2));
  clip-path: polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%);
  display:flex; align-items:center; justify-content:center; font-size:16px; color:#060a0f; font-weight:900;
}
.logo-text { font-family:'Barlow Condensed',sans-serif; font-weight:700; font-size:18px; letter-spacing:2px; color:var(--accent); }
.logo-sub { font-size:10px; color:var(--text2); letter-spacing:3px; }
.clock { font-family:'Share Tech Mono',monospace; font-size:14px; color:var(--text); letter-spacing:2px; }
.live-badge { display:flex; align-items:center; gap:6px; font-family:'Share Tech Mono',monospace; font-size:11px; color:var(--accent2); }
.live-dot { width:8px; height:8px; border-radius:50%; background:var(--accent2); animation: pulse 1.2s infinite; }
@keyframes pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:0.4;transform:scale(0.8)} }

.main { padding: 20px; display:flex; flex-direction:column; gap:20px; }
.section-label { font-family:'Barlow Condensed',sans-serif; font-size:11px; letter-spacing:4px; color:var(--text2); font-weight:600; margin-bottom:10px; text-transform:uppercase; }

.grid-2 { display:grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.card { background: var(--panel); border: 1px solid var(--border); padding: 18px; border-radius: 4px; }
.card-header { display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border); padding-bottom:8px; margin-bottom:12px; }
.card-title { font-family:'Barlow Condensed',sans-serif; font-size:16px; font-weight:700; color:var(--accent); letter-spacing:1px; }

.data-grid { display:grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
.data-item { background: var(--panel2); padding: 12px; border: 1px solid var(--border); }
.data-label { font-size:10px; color:var(--text2); font-family:'Barlow Condensed',sans-serif; letter-spacing:1px; }
.data-val { font-family:'Share Tech Mono',monospace; font-size:20px; color:var(--text); margin-top:4px; }
.data-val.green { color: var(--green); }
.data-val.blue { color: var(--blue); }
.data-val.yellow { color: var(--yellow); }

.channel-table { width:100%; border-collapse: collapse; margin-top: 10px; font-size: 11px; }
.channel-table th, .channel-table td { border: 1px solid var(--border); padding: 8px 10px; text-align: left; font-family:'Share Tech Mono',monospace; }
.channel-table th { background: var(--panel2); color: var(--accent); font-family:'Barlow Condensed',sans-serif; letter-spacing: 1px; }

@media (max-width: 1000px) {
  .grid-2 { grid-template-columns: 1fr; }
}
.logo-img{
    width:90px;
    height:90px;
    object-fit:contain;
    border-radius:10px;
    background:#fff;
    padding:2px;
    box-shadow:0 4px 14px rgba(56,189,248,0.2);
}
</style>
</head>
<body>

<div class="topbar">
  <div class="logo">
    <img src="/static/benderang.jpg" class="logo-img" alt="Benderang Logo">
    <div>
      <div class="logo-text">BENDERANG RTM OFFICE DASHBOARD</div>
      <div class="logo-sub">MQTT REAL-TIME MONITORING</div>
    </div>
  </div>
  <div style="display:flex; gap:20px; align-items:center;">
    <div class="live-badge"><div class="live-dot"></div> MQTT LIVE SUBSCRIPTION</div>
    <div class="clock" id="clock">--:--:--</div>
  </div>
</div>

<div class="main">
  <div class="section-label">Live Telemetry Dashboard</div>
  
  <div class="grid-2">
    <!-- KOTAK 1: POWERMETER (/sonoff_benderang) -->
    <div class="card">
      <div class="card-header">
        <div class="card-title" id="pm-title">Kotak 1: Powermeter (/sonoff_benderang)</div>
        <span id="pm-status" style="font-size:10px; padding:2px 8px; background:rgba(0,255,157,0.1); color:var(--green); border:1px solid var(--green);">CONNECTED</span>
      </div>
      <div id="pm-info" style="font-size:11px; color:var(--text2); margin-bottom:10px; font-family:'Share Tech Mono',monospace;">Waiting for MQTT data...</div>
      
      <div class="section-label" style="margin-top:10px;">Channels Metrics</div>
      <div style="overflow-x:auto;">
        <table class="channel-table">
          <thead>
            <tr>
              <th>Outlet</th>
              <th>State</th>
              <th>Power (W)</th>
              <th>Voltage (V)</th>
              <th>Current (A)</th>
              <th>Energy (kWh)</th>
            </tr>
          </thead>
          <tbody id="pm-channels">
            <tr><td colspan="6" style="text-align:center; color:var(--text2);">No device data received yet</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- KOTAK 2: IOT DISPENSER (/iotdispenser_output) -->
    <div class="card">
      <div class="card-header">
        <div class="card-title">Kotak 2: IoT Dispenser (/iotdispenser_output)</div>
        <span style="font-size:10px; padding:2px 8px; background:rgba(0,212,255,0.1); color:var(--blue); border:1px solid var(--blue);">ACTIVE</span>
      </div>
      
      <div class="data-grid">
        <div class="data-item">
          <div class="data-label">SUHU DINGIN</div>
          <div class="data-val blue" id="disp-suhu-dingin">-- °C</div>
        </div>
        <div class="data-item">
          <div class="data-label">SUHU PANAS</div>
          <div class="data-val yellow" id="disp-suhu-panas">-- °C</div>
        </div>
        <div class="data-item">
          <div class="data-label">SETPOINT (COOL / HEAT)</div>
          <div class="data-val" id="disp-setpoint" style="font-size:16px;">-- / --</div>
        </div>
        <div class="data-item">
          <div class="data-label">FLOAT SWITCH STATE</div>
          <div class="data-val" id="disp-float" style="font-size:15px;">--</div>
        </div>
        <div class="data-item">
          <div class="data-label">AUTOPUMP / CTRL PUMP</div>
          <div class="data-val" id="disp-pump" style="font-size:16px;">-- / --</div>
        </div>
        <div class="data-item">
          <div class="data-label">HEATER & COOLER STATE</div>
          <div class="data-val green" id="disp-states" style="font-size:15px;">--</div>
        </div>
      </div>
    </div>
  </div>
</div>

<script>
// Jam Real-Time
setInterval(() => {
  document.getElementById('clock').textContent = new Date().toTimeString().slice(0,8);
}, 1000);

// Fetch data dari API Backend yang disuplai oleh MQTT
async function fetchTelemetryData() {
  try {
    // 1. Ambil data Powermeter
    const resPm = await fetch('/api/powermeter');
    const pmData = await resPm.json();
    
    if (pmData && pmData.devices && pmData.devices.length > 0) {
      const dev = pmData.devices[0];
      document.getElementById('pm-title').textContent = `Kotak 1: ${dev.name || 'Powermeter'} (${dev.device_id || '-'})`;
      document.getElementById('pm-info').textContent = `Model: ${dev.product_model || '-'} | Brand: ${dev.brand || '-'} | Online: ${dev.online ? 'YES' : 'NO'}`;
      
      let htmlChannels = '';
      (dev.channels || []).forEach(ch => {
        htmlChannels += `
          <tr>
            <td>CH ${ch.outlet}</td>
            <td style="color:${ch.state==='on'?'var(--green)':'var(--red)'}">${(ch.state||'unknown').toUpperCase()}</td>
            <td>${Number(ch.power_w || 0).toLocaleString()} W</td>
            <td>${ch.voltage_v || 0} V</td>
            <td>${ch.current_a || 0} A</td>
            <td>${ch.energy_kwh || 0} kWh</td>
          </tr>
        `;
      });
      document.getElementById('pm-channels').innerHTML = htmlChannels;
    }

    // 2. Ambil data IoT Dispenser
    const resDisp = await fetch('/api/dispenser');
    const disp = await resDisp.json();
    
    document.getElementById('disp-suhu-dingin').textContent = (disp.suhuDingin ?? 0) + " °C";
    document.getElementById('disp-suhu-panas').textContent = (disp.suhuPanas ?? 0) + " °C";
    document.getElementById('disp-setpoint').textContent = `${disp.setpoint_cool ?? 0}°C / ${disp.setpoint_heat ?? 0}°C`;
    document.getElementById('disp-float').textContent = disp.float_sw_state === 0 ? "NORMAL (0)" : "TRIGGERED (1)";
    document.getElementById('disp-pump').textContent = `${disp.autopump ?? 0} / ${disp.ctrlPump ?? 0}`;
    document.getElementById('disp-states').textContent = `Heat: ${disp.sw_heat_state ?? 0} | Cool: ${disp.sw_cool_state ?? 0}`;

  } catch (err) {
    console.error("Gagal memperbarui data telemetry dari server:", err);
  }
}

// Polling interval setiap 1.5 detik ke backend FastAPI
setInterval(fetchTelemetryData, 1500);
fetchTelemetryData();
</script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    return HTML_TEMPLATE

