# ──────────────────────────── MIKROTIK API ────────────────────────────
from routeros_api import RouterOsApiPool, exceptions, api
import argparse
import sys
import json


ROS_HOST = "192.168.88.1"        # your router’s management IP

USERNAME = "pyapi_full"

PASSWORD = "python12345"

PORT     = 8728                  # 8728 if you left SSL off

def add_hotspot_user(mac: str, ip: str, time_minutes: int):
    """
    Function to add a user to the hotspot with a limited uptime.
    """
    try:
        pool = RouterOsApiPool(
            ROS_HOST,
            username=USERNAME,
            password=PASSWORD,
            port=PORT,
            plaintext_login=True
        )

        api = pool.get_api()

        print("Connected to mikrotik")

        hotspot_user = api.get_resource("/ip/hotspot/user")
        
        old = hotspot_user.get(name=mac)

        if old:
            hotspot_user.remove(id=old[0]['id'])
            print(f"Removed old user: {mac}")

        add_cmd = {
                "name"         : mac,
                "password"     : mac,
                "address"      : ip,
                "mac-address"  : mac,
                "limit-uptime" : f"{time_minutes}m",
                "profile" : "default"
            }

        hotspot_user.add(**add_cmd)
    
        print(f"User {mac} added with IP {ip} for {time_minutes} minutes.")

    except exceptions.RouterOsApiConnectionError as err:
        print(f"Cannot reach RouterOS host: {err}")
    except exceptions.RouterOsApiConnectionError as err:
        print(f"Login failed: {err}")
    finally:
        pool.disconnect()

def get_connected_hosts():
    try:
        pool = RouterOsApiPool(
            ROS_HOST,
            username=USERNAME,
            password=PASSWORD,
            port=PORT,
            plaintext_login=True
        )
        api = pool.get_api()

        host_list = api.get_resource("/ip/hotspot/host")
        hosts = host_list.get()
        print(json.dumps(hosts))
    
    except exceptions.RouterOsApiConnectionError as err:
        print(f"Cannot reach RouterOS host: {err}")
    except exceptions.RouterOsApiConnectionError as err:
        print(f"Login failed: {err}")
    finally:
        pool.disconnect()





from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from typing import Dict, List, NamedTuple
import uvicorn
import asyncio
from collections import deque
import datetime
import sys
from pathlib import Path
import subprocess
import json

# ──────────────────────────── subcommands ────────────────────────────
MIKROTIK_API = Path(__file__).with_name("mikrotik_api.py").resolve()


# ──────────────────────────── data structures ────────────────────────────
class LoginUser:
    def __init__(self, websocket: WebSocket, mac_address: str, ip_address: str):
        self.websocket = websocket
        self.mac_address = mac_address
        self.ip_address = ip_address

login_queue: asyncio.Queue[LoginUser] = asyncio.Queue()
login_waiting: deque[LoginUser] = deque()


# ──────────────────────────── helpers ────────────────────────────
async def broadcast_positions() -> None:
    """Tell each waiting client its 1‑based position and queue length."""
    length = len(login_waiting)
    for pos, item in enumerate(login_waiting, start=1):
        try:
            await item.websocket.send_json(
                {"status": "waiting", "data": {
                    "queue_pos": pos
                }}
            )
        except Exception:
            # client vanished – remove immediately
            try:
                login_waiting.remove(item)
            except ValueError:
                pass

def dequeue(item: LoginUser) -> None:
    """Remove `item` from `waiting` if present (helper for cleanup)."""
    try:
        login_waiting.remove(item)
    except ValueError:
        pass

def host_validation(mac: str, ip: str) -> bool:
    """Mikrotik host validation."""
    try:
        hosts_json = subprocess.run(
            [sys.executable, str(MIKROTIK_API), "getHosts"],
            text=True, capture_output=True, check=True
        ).stdout
        hosts_json = json.loads(hosts_json)
        return any(host["mac-address"] == mac and host["address"] == ip for host in hosts_json)
    except Exception:
        return False


# ──────────────────────────── background worker ────────────────────────────
async def login_queue_worker():
    """
    Forever:
    • wait for the next LoginUser
    • do the process from accepting coin to giving the user account on Mikrotik
    • send finish response to the websocket client
    • close connection
    """
    while True:
        item = await login_queue.get()
        await asyncio.sleep(5)

        print(f"Processing user: {item.mac_address} {item.ip_address}")
        
        try:
            add_hotspot_user(mac=item.mac_address, ip=item.ip_address, time_minutes=1)

            await item.websocket.send_json(
                {"status": "approved"}
            )

            await asyncio.sleep(5)

            await item.websocket.close(code=1000)
        except Exception as e:
            pass
            # print(f"An error occurred during login for {item.mac_address}: {e}")
            # # Optionally send an error message to the client
            # try:
            #     await item.websocket.send_json({"status": "error", "message": "Login process failed."})
            #     await item.websocket.close(code=1011) # Indicate an unexpected condition
            # except Exception:
            #     pass # Handle potential errors during error reporting
            # dequeue(item) # Still dequeue on error to prevent queue buildup, but the outcome wasn't successful
            # await broadcast_positions()
            # login_queue.task_done()

        dequeue(item)
        await broadcast_positions()
        login_queue.task_done()


# ──────────────────────────── FAST API APP ────────────────────────────
app = FastAPI()

@app.on_event("startup")
async def start_worker():
    asyncio.create_task(login_queue_worker())

@app.websocket("/request_login")
async def request_login(websocket: WebSocket):
    await websocket.accept()

    try:
        # Receive first data that includes mac address & ip address
        data = await websocket.receive_text()
        mac_address, ip_address = data.split(',')

        # Validate the data from mikrotik connected hosts
        if not host_validation(mac_address, ip_address):
            print("Host is not found. Terminating connection")
            await websocket.close(code=1003,
                           reason="MAC or IP not found; possible spoofing")
            return

        # enqueue + mirror in waiting deque
        item = LoginUser(websocket, mac_address, ip_address)
        await login_queue.put(item)
        login_waiting.append(item)

         # immediately tell everybody their new positions
        await broadcast_positions()

        # ❗ keep endpoint alive until WS closes from our side
        while True:
            await websocket.receive_text()   # ignore extra client messages
    except Exception as err:
        print("An error occured on user's login request", err)

@app.get("/")
async def home():
    return {"message": "Server Websocket Koinet aktif"}

if __name__ == '__main__':
    uvicorn.run(app, port=8080, host='192.168.88.2')