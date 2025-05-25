import asyncio
import serial
import time # For potential timing issues

class ArduinoSerial:
    def __init__(self, port, baud_rate=9600):
        self.port = port
        self.baud_rate = baud_rate
        self.ser = None
        self._coin_count = 0
        self.voltage = None # Initialize these as well
        self.current = None # Initialize these as well
        self._reader_task = None # To hold the background reading task

    @property
    def coinCount(self):
        return self._coin_count

    @coinCount.setter # <--- ADD THIS
    def coinCount(self, value):
        if not isinstance(value, int) or value < 0:
            raise ValueError("Coin count must be a non-negative integer.")
        self._coin_count = value
    
    def resetCoinCount(self):
        """
        Resets the internal coin count and sends a 'reset' command to Arduino.
        """

        # Get the current event loop
        loop = asyncio.get_running_loop()

        # Submit the blocking serial write operation to be run in a separate thread
        # This prevents blocking the asyncio event loop
        asyncio.create_task(
            loop.run_in_executor(
                None, # Use the default thread pool
                lambda: self.ser.write('reset\n'.encode('utf-8')) # Use lambda to pass args
            )
        )
        print("Submitted 'reset' command to serial port.")

    async def startSerial(self):
        print(f"Attempting to open serial port {self.port}...")
        try:
            # IMPORTANT: Initialize pyserial with a timeout.
            # This ensures that even if readline is accidentally called in a blocking way,
            # it won't wait forever, but will return after the timeout.
            # However, the primary fix is run_in_executor for asynchronous reading.
            self.ser = serial.Serial(self.port, self.baud_rate, timeout=0.1) # e.g., 0.1 seconds
            print(f"Serial port {self.port} opened successfully.")
            # Create the reader task and store it so it can be cancelled later
            self._reader_task = asyncio.create_task(self._readRawSerial())
        except serial.SerialException as e:
            print(f"Error opening serial port {self.port}: {e}")
            self.ser = None # Ensure ser is None if opening fails

    async def stopSerial(self):
        if self._reader_task:
            print("Cancelling Arduino serial reader task...")
            self._reader_task.cancel()
            try:
                await self._reader_task # Await until it's actually cancelled
            except asyncio.CancelledError:
                pass
            print("Arduino serial reader task cancelled.")

        if self.ser and self.ser.is_open:
            print(f"Closing serial port {self.port}...")
            self.ser.close()
            print(f"Serial port {self.port} closed.")


    async def _readRawSerial(self):
        loop = asyncio.get_running_loop()
        print("Starting raw serial reader task...")
        while True:
            try:
                # Use loop.run_in_executor to run the blocking readline call in a separate thread.
                # `None` means use the default ThreadPoolExecutor.
                # We still check in_waiting first to avoid unnecessary executor calls if no data.
                if self.ser and self.ser.is_open and self.ser.in_waiting > 0:
                    read_data = await loop.run_in_executor(None, self.ser.readline)
                    decoded_read = read_data.decode('utf-8').strip()
                    # print(f"Serial raw value: {decoded_read}") # Uncomment for debugging

                    values = decoded_read.split(',')
                    # Ensure you have enough values to avoid IndexError
                    if len(values) >= 3:
                        try:
                            self.voltage = float(values[0])
                            self.current = float(values[1])
                            self.coinCount = int(values[2])
                            # else:
                                # print(f"Received coin count {new_coin_count}, no change (current: {self._coin_count})")
                        except ValueError as ve:
                            print(f"Error parsing serial values: {ve} - Raw: '{decoded_read}'")
                        except IndexError as ie:
                            print(f"Not enough values in serial data: {ie} - Raw: '{decoded_read}'")
                    else:
                        print(f"Incomplete serial data received: '{decoded_read}'")

                # Always yield control to the event loop, even if no data was read.
                # This ensures other asyncio tasks get a chance to run.
                await asyncio.sleep(0.01)

            except serial.SerialException as e:
                print(f"Serial communication error in _readRawSerial: {e}")
                # Re-attempt connection or raise a more critical error if needed
                break # Exit the loop on critical serial error
            except asyncio.CancelledError:
                print("Arduino serial reader task was cancelled.")
                break # Essential to break out of the loop when cancelled
            except Exception as e:
                print(f"An unexpected error occurred in _readRawSerial: {e}")
                break # Catch any other unexpected errors and exit