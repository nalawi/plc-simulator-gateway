"""Demo PLC simulator exposing process values through Modbus TCP."""
import asyncio
import math
import random
import time

from pymodbus.server import StartAsyncTcpServer
from pymodbus.datastore import ModbusServerContext, ModbusDeviceContext, ModbusSequentialDataBlock

HOST = "0.0.0.0"
PORT = 5020

# Holding registers:
# 0 motor_running (0/1)
# 1 temperature in tenths C
# 2 pressure in tenths bar
# 3 flow in tenths L/min
# 4 alarm_active (0/1)
# 5 total runtime minutes
store = ModbusSequentialDataBlock(0, [1, 650, 45, 1250, 0, 0])
device = ModbusDeviceContext(hr=store)
context = ModbusServerContext(devices={1: device}, single=False)

async def update_process_values():
    start = time.monotonic()
    while True:
        elapsed = time.monotonic() - start
        motor_running = 1
        temperature = int((63.0 + 3.0 * math.sin(elapsed / 18.0) + random.uniform(-0.3, 0.3)) * 10)
        pressure = int((4.5 + 0.25 * math.sin(elapsed / 10.0) + random.uniform(-0.03, 0.03)) * 10)
        flow = int((125.0 + 8.0 * math.sin(elapsed / 7.0) + random.uniform(-1.0, 1.0)) * 10)
        alarm = 1 if temperature >= 680 else 0
        runtime_minutes = int(elapsed // 60)

        # Pymodbus server context uses device id 1, holding-register address 0.
        context[1].setValues(3, 0, [
            motor_running,
            max(0, min(65535, temperature)),
            max(0, min(65535, pressure)),
            max(0, min(65535, flow)),
            alarm,
            min(65535, runtime_minutes),
        ])
        await asyncio.sleep(1)

async def main():
    updater = asyncio.create_task(update_process_values())
    print(f"PLC Simulator listening on Modbus TCP {HOST}:{PORT}")
    try:
        await StartAsyncTcpServer(context=context, address=(HOST, PORT))
    finally:
        updater.cancel()

if __name__ == "__main__":
    asyncio.run(main())
