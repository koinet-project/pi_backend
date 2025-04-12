from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from typing import Dict
import uvicorn
import asyncio
import datetime

app = FastAPI()

API_KEY = "arie-anggara123"

# Store active clients & connected time stamp
active_connections: Dict[WebSocket, Dict[str, datetime]] = {}

def verify_api_key(api_key: str = Query(..., alias="api_key")):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    return api_key

@app.get("/")
async def home():
    return {"message": "Server Websocket Koinet aktif"}

"""
Send ping to clients every 10 seconds.

"""
@app.websocket("/ping")
async def websocket_ping(websocket: WebSocket, api_key: str = Query(...)):
    if api_key != API_KEY:
        await websocket.close(code=1008) # 1008: Close with policy violation
        return

    await websocket.accept()
    connect_timestamp = datetime.datetime.utcnow()
    active_connections[websocket] = {
        "api_key": api_key,
        "connect_timestamp": connect_timestamp
    } # Add client to list of active connections
    print(f"New client connected. Timestamp {connect_timestamp}")

    try:
        while True:
            await websocket.send_text("!!!")
            await asyncio.sleep(10)
    except WebSocketDisconnect:
        print("Client disconnected")
        del active_connections[websocket]

"""
Create a background worker to checks for client
and remove clients that exceed 1 hours in connection
"""
async def remove_long_connections():
    while True:
        await asyncio.sleep(300) # Checks every 5 minutes

        now = datetime.datetime.utcnow()
        stale_connections = [ws for ws, data in active_connections.items() if (now - data["connect_timestamp"]).total_seconds() > 3600]

        for websocket in stale_connections:
            print("Closing stale connection")
            await websocket.close(code=1000)
            del active_connections[websocket]

@app.on_event("startup")
async def startup_task():
    asyncio.create_task(remove_long_connections())


if __name__ == '__main__':
    uvicorn.run(app, port=8080, host='0.0.0.0')