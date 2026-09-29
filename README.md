# PLC Simulator + PLC Gateway REST API

This project contains two separate Python services:

1. **PLC Simulator** — simulates a PLC over Modbus TCP. It exposes holding registers and updates sample process values.
2. **PLC Gateway** — reads the simulated PLC using Modbus TCP, maps registers to named values, caches the latest readings, and exposes a REST API.

This is a development/demo simulator, not a safety-rated control system and not a substitute for a real PLC.

## Architecture

    Dashboard / DXH / Application
               |
          HTTP REST API
               |
       PLC Gateway (FastAPI)
               |
          Modbus TCP
               |
        PLC Simulator

## Register map

Modbus holding registers are zero-based in this demo:

| Address | Name | Encoding |
|---:|---|---|
| 0 | motor_running | 0 = stopped, 1 = running |
| 1 | motor_temperature_c | integer, tenths of °C (e.g. 652 = 65.2 °C) |
| 2 | water_pressure_bar | integer, tenths of bar (e.g. 45 = 4.5 bar) |
| 3 | flow_rate_lpm | integer, tenths of L/min (e.g. 1258 = 125.8 L/min) |
| 4 | alarm_active | 0 = no alarm, 1 = alarm |
| 5 | total_runtime_minutes | unsigned integer |

## Run locally

Requires Python 3.10+.

### Terminal 1: start simulator

    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    python plc_simulator.py

Simulator Modbus TCP listens on `0.0.0.0:5020` (port 5020 is used to avoid requiring root/admin privileges).

### Terminal 2: start gateway

In a second terminal, activate the same virtual environment, then run:

    export PLC_HOST=127.0.0.1
    export PLC_PORT=5020
    export API_KEY=demo-change-me
    uvicorn gateway:app --host 0.0.0.0 --port 8000

### Test API

    curl http://127.0.0.1:8000/api/v1/health
    curl -H "X-API-Key: demo-change-me" http://127.0.0.1:8000/api/v1/plcs
    curl -H "X-API-Key: demo-change-me" http://127.0.0.1:8000/api/v1/plcs/plc-demo-01/status
    curl -H "X-API-Key: demo-change-me" http://127.0.0.1:8000/api/v1/plcs/plc-demo-01/telemetry

Interactive API docs: http://127.0.0.1:8000/docs

## Run with Docker Compose

    docker compose up --build

Then call the API on port 8000. The API key defaults to `demo-change-me` in the compose file; change it for any shared environment.

## Important notes

- This simulator speaks Modbus TCP, not Siemens S7 or OPC UA. It lets you develop and test the gateway-to-REST layer without real hardware.
- For a real Siemens PLC, replace the Modbus adapter in `gateway.py` with an OPC UA or supported S7 driver based on the exact CPU model, firmware, and enabled protocols.
- The gateway is read-only: it exposes no endpoint to write to PLC registers.
- Keep PLC/OT networks isolated. Do not expose Modbus TCP or this demo API directly to the public internet.
- The demo API key is a simple example only. Use TLS termination, proper secret management, network restrictions, and stronger authentication for production.
