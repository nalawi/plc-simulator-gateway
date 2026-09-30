"""Demo PLC simulator exposing process values through Modbus TCP."""
import asyncio
import math
import random
import time

from pymodbus.server import StartAsyncTcpServer
from pymodbus.simulator import DataType, SimData, SimDevice

HOST = "0.0.0.0"
PORT = 5020

# Holding registers:
# 0 motor_running (0/1)
# 1 temperature in tenths C
# 2 pressure in tenths bar
# 3 flow in tenths L/min
# 4 alarm_active (0/1)
# 5 total runtime minutes
START_VALUES = [1, 650, 45, 1250, 0, 0]
START = time.monotonic()


def compute_values() -> list[int]:
    """Compute the current simulated process values."""
    elapsed = time.monotonic() - START
    motor_running = 1
    temperature = int((63.0 + 3.0 * math.sin(elapsed / 18.0) + random.uniform(-0.3, 0.3)) * 10)
    pressure = int((4.5 + 0.25 * math.sin(elapsed / 10.0) + random.uniform(-0.03, 0.03)) * 10)
    flow = int((125.0 + 8.0 * math.sin(elapsed / 7.0) + random.uniform(-1.0, 1.0)) * 10)
    alarm = 1 if temperature >= 680 else 0
    runtime_minutes = int(elapsed // 60)
    return [
        motor_running,
        max(0, min(65535, temperature)),
        max(0, min(65535, pressure)),
        max(0, min(65535, flow)),
        alarm,
        min(65535, runtime_minutes),
    ]


async def refresh_action(
    function_code: int,
    start_address: int,
    address: int,
    count: int,
    current_registers: list[int],
    set_values: list[int] | list[bool] | None,
):
    """Refresh the simulated process values on every Modbus read.

    The action callback receives the live register list of the device;
    mutating it in place changes what the server responds with.
    """
    if set_values is None:  # read request
        current_registers[:] = compute_values()
    return None


device = SimDevice(
    id=1,
    simdata=[
        SimData(address=0, values=START_VALUES, datatype=DataType.REGISTERS)
    ],
    action=refresh_action,
)


async def main():
    print(f"PLC Simulator listening on Modbus TCP {HOST}:{PORT}")
    await StartAsyncTcpServer(context=device, address=(HOST, PORT))


if __name__ == "__main__":
    asyncio.run(main())