from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
import uvicorn
import asyncio
from asyncio import Queue, QueueEmpty
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────── Class Imports ────────────────────────────
from arduino.arduino_serial import ArduinoSerial
from mikrotik_comm.mikrotik_comm import MikrotikAPI
from firebase.database import DatabaseAPI
import json

# ──────────────────────────── MIKROTIK API ────────────────────────────
ROS_HOST = "192.168.88.1"        # your router’s management IP
USERNAME = os.getenv("MIKROTIK_API_USER")
PASSWORD = os.getenv("MIKROTIK_API_PASS")
PORT     = 8728                  # 8728 if you left SSL off
mikrotik_api = MikrotikAPI(ROS_HOST, USERNAME, PASSWORD, PORT)

# ──────────────────────────── COIN - DUINO ────────────────────────────
dev_port = "COM6" # Change to actual device port
arduino = ArduinoSerial(dev_port)

# ──────────────────────────── FIREBASE ────────────────────────────
db = DatabaseAPI(
    './src/koinet-8bbee-firebase-adminsdk-fbsvc-3745e3e8c0.json',
    'https://koinet-8bbee-default-rtdb.asia-southeast1.firebasedatabase.app/'
    )

lock_db = False # Lock database update if the database is currently updated.
#TEST
# ──────────────────────────── data structures ────────────────────────────
class LoginUser:
        def __init__ (self, websocket: WebSocket, mac_address: str, ip_address: str):
            self.websocket = websocket
            self.mac_address = mac_address
            self.ip_address = ip_address
            self.done = asyncio.Event()

login_queue: Queue[LoginUser] = Queue(maxsize = 0)

# ──────────────────────────── helpers ────────────────────────────
import asyncio

async def broadcast_positions() -> None:
    """Tell each waiting client its position on the queue."""
    temp_items = []
    # No need for queue_pos = 0 here initially, we'll calculate it later

    # Drain the queue into a temporary list
    # The logic here is fine for getting all current items
    while True:
        try:
            item = await asyncio.wait_for(login_queue.get(), timeout=0.01)
            temp_items.append(item)
        except asyncio.TimeoutError:
            break
        except Exception as e:
            print(f"Error draining queue: {e}")
            break

    # Now iterate through the temporary list to broadcast and then put back
    # The first waiting client should be position 1 (since position 0 is "in process")
    # or you might want to consider 0 as the next-in-line
    # If 0 is "current processing", then the first one in the queue is #1
    start_pos_for_waiting_clients = 2 # <--- THE KEY CHANGE IS HERE!

    for i, item in enumerate(temp_items): # Use enumerate to get index
        try:
            current_client_queue_pos = start_pos_for_waiting_clients + i # Offset by 1

            await item.websocket.send_json(
                {"status": "waiting", "data": {
                    "queue_pos": current_client_queue_pos
                }}
            )
            # Put the item back into the queue
            await login_queue.put(item)
            # queue_pos increment is now implicit with enumerate(i) + offset
        except Exception as e:
            print(f"An error occurred when broadcasting to clients: {e}")
            # Ensure it's put back even on send error
            await login_queue.put(item)

    if not temp_items:
        print("Queue is empty, no positions to broadcast.")

async def update_coin_count(websocket, count):
    await websocket.send_json(
        {"status": "receiving", "data": {
            "coin_count": count,
            }
        }
    )

# ──────────────────────────── background worker ────────────────────────────
timeout_duration = 11  # Add 1 lag second

async def _timer_task(item: LoginUser, timeout_duration_seconds: int, stop_event: asyncio.Event):
    """
    A standalone async function for managing a user's timer.
    This makes it more self-contained and testable.
    """
    timeout_start = datetime.now() # Base time for the current timer window
    last_coin_count = arduino.coinCount

    # Calculate remaining for the initial print statement
    initial_end_time = timeout_start + timedelta(seconds=timeout_duration_seconds)
    initial_remaining = (initial_end_time - datetime.now()).total_seconds()

    print(f"[{item.mac_address}] _timer_task started. Initial remaining: {int(initial_remaining)}s")


    while True:
        # Recalculate end_time every iteration if timeout_start can change
        # This is critical for extending the timer when coins are added.
        end_time = timeout_start + timedelta(seconds=timeout_duration_seconds)
        now = datetime.now()
        remaining = (end_time - now).total_seconds()

        # Add this print back to see loop progress
        print(f"[{item.mac_address}] _timer_task loop: remaining={remaining:.2f}s, now={now}, end_time={end_time}")

        if remaining <= 0:
            print(f"[{item.mac_address}] Timer expired (remaining <= 0). Breaking loop.")
            break # Timer has expired

        # Check for new coins, extending the timer if detected
        if arduino.coinCount > last_coin_count:
            print(f"[{item.mac_address}] Coin detected for {item.mac_address}. Extending timer.")
            last_coin_count = arduino.coinCount
            timeout_start = datetime.now() # Reset timer base to now
            # CRITICAL: Recalculate end_time immediately after extending timeout_start
            # to ensure the first 'remaining' in the next loop iteration is correct
            end_time = timeout_start + timedelta(seconds=timeout_duration_seconds)
            remaining = (end_time - datetime.now()).total_seconds() # Update remaining after extension

        try:
            # Send current timer and coin count to the client
            # ... (rest of your send_json logic) ...
            await item.websocket.send_json(
                {
                    "status": "receiving",
                    "data": {
                        "timer": int(remaining),
                        "coin_count": arduino.coinCount,
                    }
                }
            )
            print(f"[{item.mac_address}] Sent timer update: {int(remaining)}s, coins: {arduino.coinCount}")

        except Exception as e:
            print(f"[{item.mac_address}] WebSocket closed or failed for {item.mac_address}: {e}")
            if not stop_event.is_set():
                stop_event.set()
            return # Exit the timer task early if the socket is closed

        # Yield control to the event loop
        await asyncio.sleep(1) # Check every second

    # If the loop breaks (timer expired naturally), set the stop_event
    if not stop_event.is_set():
        print(f"[{item.mac_address}] _timer_task naturally finished (timer expired). Setting stop_event.")
        stop_event.set()


async def login_queue_worker():
    while True:
        item: LoginUser | None = None # Explicit type hint for clarity
        try:
            item = login_queue.get_nowait()
        except QueueEmpty:
            # If the queue is empty, yield control to prevent 100% CPU usage
            await asyncio.sleep(0.1) # Small sleep to let other tasks run
            continue # Go back to the start of the while loop
        except Exception as e:
            print(f"Failed receiving queue item: {e}")
            await asyncio.sleep(1) # Sleep on other errors too
            continue # Go back to the start of the while loop

        if item is not None:
            stop_event = asyncio.Event() # Renamed from stopEvent for PEP8 compliance

            print(f"Processing login request for {item.mac_address} at {datetime.now()}")

            # Start the timer task
            timer_task = asyncio.create_task(
                _timer_task(item, timeout_duration, stop_event)
            )

            try:
                await stop_event.wait() # Wait for the timer task to signal completion/stop
                print(f"Timer for {item.mac_address} completed/stopped.")

                # Ensure the timer task is cancelled if it's still running (e.g., if stop_event was set externally)
                if not timer_task.done():
                    timer_task.cancel()
                    try:
                        await timer_task # Await cancellation to avoid Task exception was never retrieved
                    except asyncio.CancelledError:
                        pass

                # --- Logic after timer completion ---
                if arduino.coinCount == 0: # Note: this arduino.coinCount check might need refinement
                                           # If arduino.coinCount is a global, it affects ALL clients.
                                           # You might want to track coins for THIS specific item/session.
                    print("Queue finished. No coin is accepted")
                    await item.websocket.send_json({"status": "denied", "reason": "no coin"})
                else:
                    time_minutes = arduino.coinCount * 30
                    print(f"Approving login for {item.mac_address} for {time_minutes} minutes.")
                    mikrotik_api.addHotspotUser(item.mac_address, item.ip_address, time_minutes)
                    await asyncio.sleep(0.1)
                    await item.websocket.send_json({"status": "approved", "time_minutes": time_minutes})

                    # Finish queue. Broadcast positions to other
                    await broadcast_positions()

                item.done.set() # Signal the request_login task that this item is done
                arduino.resetCoinCount()

            except asyncio.CancelledError:
                # This worker task itself might be cancelled if the server shuts down
                print(f"Login worker for {item.mac_address} was cancelled.")
                if not item.done.is_set():
                    item.done.set() # Ensure the original request is unblocked
            except Exception as e:
                # Catch specific exceptions if possible, otherwise general Exception
                print(f"An error occurred during login for {item.mac_address}: {e}")
                # Ensure the item.done event is set even on error to unblock the client
                if not item.done.is_set():
                    item.done.set()
                # Consider what to do with the item in the queue if an error occurs:
                # Do you put it back? Do you try again? Or is it a terminal error?

async def plts_status_worker():
    while True:
        if arduino.voltage is None or arduino.current is None:
            print("Cannot update PLTS Status: Data from Arduino is received as NoneType, skipping current loop.")
        else:
            db.updatePltsStatus(
                arduino.voltage,
                arduino.current,
            )
        
        await asyncio.sleep(60)

async def connected_users_worker():
    while True:
        if lock_db:
            continue

        allUsers = mikrotik_api.getHotspotUsers()

        activeUsers = mikrotik_api.getHotspotActive()
        
        db.updateConnectedUsers(allUsers, activeUsers)

        await asyncio.sleep(2)

# ──────────────────────────── FAST API APP ────────────────────────────
app = FastAPI()

@app.on_event("startup")
async def start_worker():
    asyncio.create_task(login_queue_worker())
    await arduino.startSerial()
    await asyncio.sleep(1)
    asyncio.create_task(plts_status_worker())
    asyncio.create_task(connected_users_worker())
    print("FastAPI Server startup session completed.")

@app.on_event("shutdown")
async def shutdown_worker():
    print("FastAPI Server shutting down...")
    await arduino.stopSerial() # Call your new stopSerial method
    print("FastAPI Server shutdown completed.")

@app.websocket("/request_login")
async def request_login(websocket: WebSocket):
    await websocket.accept()

    try:
        # Receive first data that includes mac address & ip address
        data = await websocket.receive_text()
        mac_address, ip_address = data.split(',')

        # Validate the data from mikrotik connected hosts
        if not mikrotik_api.checkHostConnected(mac_address, ip_address):
            print("Host is not found. Terminating connection")
            await websocket.close(code=1003,
                           reason="MAC or IP not found; possible spoofing")
            return
        
        # Check if the user already have account on mikrotik
        users = json.loads(mikrotik_api.getHotspotUsers())
        for user in users:
            if user.get('mac-address') == mac_address and user.get('address') == ip_address:
                await websocket.send_json(
                    {"status": "bypass", "data": {
                        "login": "approved"
                    }}
                )
                print("User already have quota. Skip login session")
                return
        
        print("Host detected. Adding client to queue.")

        # enqueue + mirror in waiting deque
        item = LoginUser(websocket, mac_address, ip_address)
        await login_queue.put(item)

        # immediately tell everybody their new positions
        await broadcast_positions()

        await item.done.wait()
    except Exception as err:
        print("An error occured on user's login request", err)

@app.get("/")
async def home():
    return {"message": "Server Websocket Koinet aktif"}

if __name__ == '__main__':
    uvicorn.run(app, port=8080, host='192.168.88.2')