import asyncio
from arduino.arduino_serial import ArduinoSerial

async def main():
    arduino = ArduinoSerial('COM6')
    await arduino.startSerial()

    while True:
        print(f"Voltage: {arduino.voltage} V, Current: {arduino.current} A, Coins: {arduino.coinCount}")
        await asyncio.sleep(1)

asyncio.run(main())