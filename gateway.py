"""Read-only Modbus TCP gateway that exposes REST/JSON telemetry."""
import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pymodbus.client import AsyncModbusTcpClient

PLC_HOST = os.getenv("PLC_HOST", "127.0.0.1")
PLC_PORT = int(os.getenv("PLC_PORT", "5020"))
PLC_DEVICE_ID = int(os.getenv("PLC_DEVICE_ID", "1"))
POLL_INTERVAL = float(os.getenv("POLL_INTERVAL", "1.0"))
API_KEY = os.getenv("API_KEY", "demo-change-me")
PLC_ID = os.getenv("PLC_ID", "plc-demo-01")
# Comma-separated list of allowed CORS origins. Use "*" (default) to allow any origin.
CORS_ORIGINS = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "*").split(",") if origin.strip()]

cache: dict[str, Any] = {
    "plc_id": PLC_ID,
    "connection_status": "disconnected",
    "timestamp": None,
    "data": {},
    "errors": [],
}

def require_api_key(x_api_key: str | None = Header(default=None)):
    if not API_KEY or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Missing or invalid X-API-Key")

async def poll_plc():
    while True:
        client = AsyncModbusTcpClient(PLC_HOST, port=PLC_PORT, timeout=2)
        try:
            connected = await client.connect()
            if not connected:
                raise ConnectionError(f"Cannot connect to PLC at {PLC_HOST}:{PLC_PORT}")

            cache["connection_status"] = "connected"
            while True:
                result = await client.read_holding_registers(
                    address=0, count=6, device_id=PLC_DEVICE_ID
                )
                if result.isError():
                    raise RuntimeError(f"Modbus read error: {result}")

                r = result.registers
                cache["data"] = {
                    "motor_running": bool(r[0]),
                    "motor_temperature_c": r[1] / 10.0,
                    "water_pressure_bar": r[2] / 10.0,
                    "flow_rate_lpm": r[3] / 10.0,
                    "alarm_active": bool(r[4]),
                    "total_runtime_minutes": r[5],
                }
                cache["timestamp"] = datetime.now(timezone.utc).isoformat()
                cache["errors"] = []
                await asyncio.sleep(POLL_INTERVAL)

        except asyncio.CancelledError:
            client.close()
            raise
        except Exception as exc:
            cache["connection_status"] = "disconnected"
            cache["errors"] = [{"message": str(exc)}]
            await asyncio.sleep(3)
        finally:
            client.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(poll_plc())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

app = FastAPI(
    title="PLC Gateway REST API",
    description="Read-only REST API for telemetry from a PLC over Modbus TCP.",
    version="1.0.0",
    lifespan=lifespan,
)

# Allow browsers to call the API from other origins (configure via CORS_ORIGINS).
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/v1/health")
async def health():
    return {
        "api_status": "running",
        "plc_status": cache["connection_status"],
        "timestamp": cache["timestamp"],
    }

@app.get("/api/v1/plcs", dependencies=[Depends(require_api_key)])
async def list_plcs():
    return [{
        "plc_id": PLC_ID,
        "protocol": "Modbus TCP",
        "host": PLC_HOST,
        "port": PLC_PORT,
        "connection_status": cache["connection_status"],
    }]

@app.get("/api/v1/plcs/{plc_id}/status", dependencies=[Depends(require_api_key)])
async def plc_status(plc_id: str):
    check_plc_id(plc_id)
    return {
        "plc_id": PLC_ID,
        "connection_status": cache["connection_status"],
        "last_update": cache["timestamp"],
        "errors": cache["errors"],
    }

@app.get("/api/v1/plcs/{plc_id}/tags", dependencies=[Depends(require_api_key)])
async def list_tags(plc_id: str):
    check_plc_id(plc_id)
    return {
        "motor_running": {"register": 0, "type": "boolean"},
        "motor_temperature_c": {"register": 1, "type": "float", "scale": 0.1},
        "water_pressure_bar": {"register": 2, "type": "float", "scale": 0.1},
        "flow_rate_lpm": {"register": 3, "type": "float", "scale": 0.1},
        "alarm_active": {"register": 4, "type": "boolean"},
        "total_runtime_minutes": {"register": 5, "type": "integer"},
    }

@app.get("/api/v1/plcs/{plc_id}/telemetry", dependencies=[Depends(require_api_key)])
async def telemetry(plc_id: str):
    check_plc_id(plc_id)
    if cache["connection_status"] != "connected" or not cache["timestamp"]:
        raise HTTPException(status_code=503, detail={
            "message": "PLC is not connected or no telemetry has been received yet",
            "errors": cache["errors"],
        })
    return {
        "plc_id": PLC_ID,
        "connection_status": cache["connection_status"],
        "timestamp": cache["timestamp"],
        "data": cache["data"],
        "errors": cache["errors"],
    }

def check_plc_id(plc_id: str):
    if plc_id != PLC_ID:
        raise HTTPException(status_code=404, detail="PLC not found")
