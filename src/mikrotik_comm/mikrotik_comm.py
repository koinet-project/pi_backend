from routeros_api import RouterOsApiPool, exceptions, api

import argparse
import sys
import json

ROS_HOST = "192.168.88.1"        # your router’s management IP

USERNAME = "pyapi_full"

PASSWORD = "python12345"

PORT     = 8728                  # 8728 if you left SSL off

class MikrotikAPI:
    def __init__(self, host: str, username: str, password: str, port: str = "8728"):
        self._host = host
        self._username = username
        self._password = password
        self._port = port

        self._connectToAPI()

    def _connectToAPI(self):
        try:
            self._pool = RouterOsApiPool(
                self._host,
                self._username,
                self._password,
                self._port,
                plaintext_login=True
            )
        except Exception as e:
            print("Exception when connecting to RouterOS API: " + e)

    def _disconnectAPI(self):
        try:
            self._pool.disconnect()
        except Exception as e:
            print("Failed to disconnect from API: " + e)

    def getHotspotUsers(self) -> str:
        try:
            api = self._pool.get_api()

            host_list = api.get_resource("/ip/hotspot/user")
            hosts = host_list.get()

            return json.dumps(hosts)
        except exceptions.RouterOsApiConnectionError as err:
            print(f"Cannot reach RouterOS host: {err}")
        except exceptions.RouterOsApiConnectionError as err:
            print(f"Login failed: {err}")

    def getHotspotActive(self) -> str:
        try:
            api = self._pool.get_api()

            active_list = api.get_resource("/ip/hotspot/active")
            active = active_list.get()
            
            return json.dumps(active)
        except exceptions.RouterOsApiConnectionError as err:
            print(f"Cannot reach RouterOS host: {err}")
        except exceptions.RouterOsApiConnectionError as err:
            print(f"Login failed: {err}")

    def getHotspotHosts(self) -> str:
        try:
            api = self._pool.get_api()

            host_list = api.get_resource("/ip/hotspot/host")
            hosts = host_list.get()

            return json.dumps(hosts)
        except exceptions.RouterOsApiConnectionError as err:
            print(f"Cannot reach RouterOS host: {err}")
        except exceptions.RouterOsApiConnectionError as err:
            print(f"Login failed: {err}")

    def checkHostConnected(self, mac: str, ip: str):
        try:
            hosts = self.getHotspotHosts()
            hosts = json.loads(hosts)

            return any(host["mac-address"] == mac and host["address"] == ip for host in hosts)
        except:
            print("Exception: No connected Host of such mac / ip address")
            return False


    def getRouterInfo(self):
        try:
            api = self._pool.get_api()

            system = api.get_resource("/system/resource")
            info = system.get()[0]
            print(f"Model: {info['board-name']}  OS: {info['version']}")
            print("Mikrotik connection test successful")
        except exceptions.RouterOsApiConnectionError as err:
            print(f"Cannot reach RouterOS host: {err}")
        except exceptions.RouterOsApiConnectionError as err:
            print(f"Login failed: {err}")

    def addHotspotUser(self, mac: str, ip: str, time_minutes: int):
        try:
            command = {
                "name"         : mac,
                "password"     : mac,
                "mac-address"  : mac,
                "address"      : ip,
                "limit-uptime" : f"{time_minutes}m",
                "profile" : "default"
            }
            
            api = self._pool.get_api()

            api.get_resource("/ip/hotspot/user").add(**command)

            print(f"User {mac} added with IP {ip} for {time_minutes} minutes.")
        except exceptions.RouterOsApiConnectionError as e:
            print(f"Cannot reach RouterOS host: {e}")
        except exceptions.RouterOsApiConnectionError as e:
            print(f"Login failed: {e}")
    


            


