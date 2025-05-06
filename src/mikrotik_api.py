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

        add_cmd = {
                "name"         : mac,
                "mac-address"  : mac,
                "address"      : ip,
                "limit-uptime" : f"{time_minutes}m",
                "profile" : "koinet_universal"
            }

        api.get_resource("/ip/hotspot/user").add(**add_cmd)
    
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


def get_router_info():
    """
    Function to retrieve and print router's system resource info.
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

        system = api.get_resource("/system/resource")
        info = system.get()[0]
        print(f"Model: {info['board-name']}  OS: {info['version']}")
        print("Mikrotik connection test successful")
    
    except exceptions.RouterOsApiConnectionError as err:
        print(f"Cannot reach RouterOS host: {err}")
    except exceptions.RouterOsApiConnectionError as err:
        print(f"Login failed: {err}")
    finally:
        pool.disconnect()


def build_parser() -> argparse.ArgumentParser:
    """
    Build the argument parser with subcommands for different functionalities.
    """
    parser = argparse.ArgumentParser(
        prog="sub.py",
        description="RouterOS API functions"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ---- add hotspot user ----
    hotspot_parser = subparsers.add_parser("allowUserToHotspot", help="Add user to hotspot")
    hotspot_parser.add_argument("--mac", required=True, help="MAC address")
    hotspot_parser.add_argument("--ip", required=True, help="IP address")
    hotspot_parser.add_argument("--time_minutes", type=int, default=1, help="Uptime limit in minutes")

    # ---- get router info ----
    info_parser = subparsers.add_parser("getRouterInfo", help="Get router system information")

    return parser


def build_parser() -> argparse.ArgumentParser:
    """
    Build the argument parser with subcommands for different functionalities.
    """
    parser = argparse.ArgumentParser(
        prog="sub.py",
        description="RouterOS API functions"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ---- add hotspot user ----
    hotspot_parser = subparsers.add_parser("allowUserToHotspot", help="Add user to hotspot")
    hotspot_parser.add_argument("--mac", required=True, help="MAC address")
    hotspot_parser.add_argument("--ip", required=True, help="IP address")
    hotspot_parser.add_argument("--time_minutes", type=int, default=1, help="Uptime limit in minutes")

    # ---- get router info ----
    info_parser = subparsers.add_parser("getRouterInfo", help="Get router system information")

    # ---- get connected hosts on the hotspot ----
    hosts_parser = subparsers.add_parser("getHosts", help="Get the currently connected hosts")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "allowUserToHotspot":
        add_hotspot_user(args.mac, args.ip, args.time_minutes)
    elif args.command == "getRouterInfo":
        get_router_info()
    elif args.command == "getHosts":
        get_connected_hosts()
    else:
        print("Invalid command")

if __name__ == "__main__":
    main()