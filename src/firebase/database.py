import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
from datetime import datetime
import json
import re

class DatabaseAPI:
    def __init__(self, cert: str, url: str):
        self._cred = credentials.Certificate(cert)
        self._url = url

        self._lastSampleTime = None
        self._hourlySample = []

        self._connectToFirebase()
    
    def _connectToFirebase(self):
        firebase_admin.initialize_app(self._cred, {
            'databaseURL': self._url
        })

    def updatePltsStatus(self, voltage: float, current: float):
        now = datetime.now()

        if voltage < 0.0:
            voltage = 0.0
        
        if current < 0.0:
            current = 0.0

        power = current * voltage

        ref = db.reference('/monitoring/pltsStatus/')
        ref.update({
            'currentAmpere': current,
            'currentVoltage': voltage
        })

        # Handle initial sample or hourly transition
        if self._lastSampleTime is None:
            self._lastSampleTime = now
            self._hourlySample.append(power)
            print(f"Initial sample added: {power}W")
            return

        # Check for hour change (new hour started)
        if now.hour != self._lastSampleTime.hour:
            print(f"Hour changed from {self._lastSampleTime.hour} to {now.hour}. Processing hourly samples.")
            self._updateHourlySample(hour = now.hour)
            self._lastSampleTime = now
            self._hourlySample.append(power) # Start new hour's sample
            print(f"New hour's initial sample added: {power}W")
            return

        # Check for regular sample interval
        # Use total_seconds() for robust comparison regardless of date/time components
        time_since_last_sample = (now - self._lastSampleTime).total_seconds()
        if time_since_last_sample >= 300:
            self._hourlySample.append(power)
            self._lastSampleTime = now
            print(f"Sample added after {time_since_last_sample:.0f}s interval: {power}W")
            return

    def _updateHourlySample(self, hour: int):
        ref = db.reference(f'/monitoring/pltsStatus/hourlyPowerOutput/{hour}')

        powerOutput = sum(self._hourlySample) * (5 / 60) # Sum of samples divided by 5 minutes every sample.

        ref.set(powerOutput)
    
    def _parse_mikrotik_time(self, timestr):
        if timestr in ("", "never"):
            return 0

        time_units = {
            'w': 7 * 24 * 3600,
            'd': 24 * 3600,
            'h': 3600,
            'm': 60,
            's': 1
        }

        total_seconds = 0
        pattern = r'(\d+)([wdhms])'
        matches = re.findall(pattern, timestr)

        for value, unit in matches:
            total_seconds += int(value) * time_units[unit]

        return total_seconds

    def updateConnectedUsers(self, all_users: str, active_users: str):
        users = json.loads(all_users)
        actives = json.loads(active_users)

        # First check for active users before checking all users
        updateList = []
        for user in actives:
            ref = db.reference(f'/monitoring/connectedUsers/{user.get('user')}')

            ref.update({
                'userIP': user.get('address'),
                'userMAC': user.get('mac-address'),
                'uptime': self._parse_mikrotik_time(user.get('session-time-left')),
            })

            updateList.append(user.get('user'))
            
        for user in users:
            # Skip Nonetype account (bug or something)
            if user.get('mac-address') is None or user.get('address') is None:
                continue

            # Only update for active users
            if user.get('name') not in updateList:
                continue

            # Skip default account
            if (user.get('name') == 'default-trial'):
                continue

            ref = db.reference(f'/monitoring/connectedUsers/{user.get('name')}')

            ref.update({
                'uptimeLimit': self._parse_mikrotik_time(user.get('limit-uptime')),
            })

        # Delete remaining user that are not active
        ref = db.reference(f'/monitoring/connectedUsers')
        dbUsers = ref.get()

        if dbUsers:
            for user in dbUsers.keys():
                print(user)
                if user not in updateList:
                    ref.child(user).delete()






