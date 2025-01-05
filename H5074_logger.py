#!/usr/bin/env python3

import asyncio
import sys
import csv
from datetime import datetime
from bleak import BleakScanner
import json
import os
from typing import Dict, Optional
import logging
from logging.handlers import RotatingFileHandler
import time

class GoveeSensor:
    def __init__(self, mac_address: Optional[str] = None):
        self.mac_address = mac_address
        self.config_file = 'govee_config.json'
        self.data_file = f'govee_data_{datetime.now().strftime("%Y%m%d")}.csv'
        self.setup_logging()
        self._last_log_time = 0
        
    def setup_logging(self):
        """Setup rotating log handler"""
        self.logger = logging.getLogger('GoveeSensor')
        self.logger.setLevel(logging.INFO)
        handler = RotatingFileHandler('govee_sensor.log', maxBytes=1024*1024, backupCount=5)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    async def scan_devices(self, timeout: int = 10) -> list:
        """Scan for Govee H5074 devices with error handling and retry"""
        try:
            self.logger.info("Starting BLE scan")
            devices = await BleakScanner.discover(timeout=timeout)
            govee_devices = []
            
            for device in devices:
                if device.name and "Govee_H5074" in device.name:
                    govee_devices.append({
                        'mac': device.address,
                        'name': device.name,
                        'rssi': device.rssi
                    })
                    self.logger.info(f"Found device: {device.name} ({device.address})")
            
            return govee_devices
        except Exception as e:
            self.logger.error(f"Scan error: {str(e)}")
            return []

    def save_config(self, mac_address: str):
        """Save device configuration with error handling"""
        try:
            config = {'mac_address': mac_address}
            with open(self.config_file, 'w') as f:
                json.dump(config, f)
            self.mac_address = mac_address
            self.logger.info(f"Configuration saved for device: {mac_address}")
        except Exception as e:
            self.logger.error(f"Error saving configuration: {str(e)}")

    def load_config(self) -> Optional[str]:
        """Load device configuration"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.mac_address = config.get('mac_address')
                    return self.mac_address
        except Exception as e:
            self.logger.error(f"Error loading configuration: {str(e)}")
        return None

    def decode_sensor_data(self, manufacturer_data: Dict) -> Optional[Dict]:
        """Decode Govee H5074 manufacturer specific data"""
        try:
            if 60552 not in manufacturer_data:
                return None
                
            data = manufacturer_data[60552]
            self.logger.debug(f"Raw manufacturer data: {data.hex()}")
            
            if len(data) < 6:
                return None
                
            temp = int.from_bytes(data[1:3], byteorder='little') / 100.0
            humidity = int.from_bytes(data[3:5], byteorder='little') / 100.0
            battery = data[5]
            
            return {
                'temperature': temp,
                'humidity': humidity,
                'battery': battery,
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'raw_hex': data.hex()
            }
        except Exception as e:
            self.logger.error(f"Error decoding sensor data: {str(e)}")
            return None

    def log_data(self, data: Dict):
        """Log sensor data to CSV with error handling"""
        try:
            file_exists = os.path.exists(self.data_file)
            with open(self.data_file, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['timestamp', 'temperature', 'humidity', 'battery', 'raw_hex'])
                if not file_exists:
                    writer.writeheader()
                writer.writerow(data)
            self.logger.info(f"Data logged: Temp={data['temperature']}°C, Humidity={data['humidity']}%")
        except Exception as e:
            self.logger.error(f"Error logging data: {str(e)}")

    async def monitor_continuous(self, interval: int = 60):
        """Continuously monitor sensor data through advertisements"""
        self._last_log_time = time.time()  # Initialize last log time
        
        def should_log() -> bool:
            current_time = time.time()
            if current_time - self._last_log_time >= interval:
                self._last_log_time = current_time
                return True
            return False

        def detection_callback(device, advertisement_data):
            if device.address.upper() == self.mac_address.upper():
                if advertisement_data.manufacturer_data and should_log():
                    data = self.decode_sensor_data(advertisement_data.manufacturer_data)
                    if data:
                        self.log_data(data)
                        print(f"\nTemperature: {data['temperature']}°C")
                        print(f"Humidity: {data['humidity']}%")
                        print(f"Battery: {data['battery']}%")
                        print(f"Next update in {interval} seconds")
                        print("-" * 40)

        print(f"\nStarting monitoring with {interval} second intervals")
        print("Press Ctrl+C to stop\n")
        
        async with BleakScanner(detection_callback=detection_callback):
            self.logger.info(f"Started monitoring device: {self.mac_address}")
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                print("\nMonitoring stopped by user")

async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Govee H5074 BLE Sensor Logger')
    parser.add_argument('--scan', action='store_true', help='Scan for available devices')
    parser.add_argument('--configure', action='store_true', help='Configure a new device')
    parser.add_argument('--monitor', action='store_true', help='Monitor sensor data')
    parser.add_argument('--interval', type=int, default=60, help='Reading interval in seconds for monitoring')
    
    args = parser.parse_args()
    sensor = GoveeSensor()
    
    if args.scan or args.configure:
        devices = await sensor.scan_devices()
        if not devices:
            print("No Govee H5074 devices found")
            return
            
        print("\nFound devices:")
        for i, device in enumerate(devices):
            print(f"{i+1}. {device['name']} (MAC: {device['mac']}, RSSI: {device['rssi']})")
            
        if args.configure:
            selection = int(input("\nSelect device number to configure: ")) - 1
            if 0 <= selection < len(devices):
                sensor.save_config(devices[selection]['mac'])
                print(f"Device configured: {devices[selection]['name']}")
            else:
                print("Invalid selection")
    
    elif args.monitor:
        mac_address = sensor.load_config()
        if not mac_address:
            print("No device configured. Please run with --configure first")
            return
            
        try:
            await sensor.monitor_continuous(args.interval)
        except KeyboardInterrupt:
            print("\nStopping monitoring")

if __name__ == "__main__":
    asyncio.run(main())
