#!/usr/bin/env python3

import asyncio
import csv
from datetime import datetime
from bleak import BleakScanner
import json
import os
from typing import Dict, List, Optional
import logging
from logging.handlers import RotatingFileHandler
import time
import re

class DeviceConfig:
    def __init__(self, config_file='device_config.json'):
        self.config_file = config_file
        self.config = self.load_config()

    def load_config(self) -> dict:
        """Load device configuration"""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                return json.load(f)
        return {"devices": []}

    def save_config(self):
        """Save current configuration"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=4)

    def get_device_by_key(self, key: str) -> Optional[dict]:
        """Get device configuration by key"""
        for device in self.config['devices']:
            if device['key'] == key:
                return device
        return None

    def get_device_by_mac(self, mac_address: str) -> Optional[dict]:
        """Get device configuration by MAC address"""
        mac_address = mac_address.upper()
        for device in self.config['devices']:
            if device['mac_address'].upper() == mac_address:
                return device
        return None

    def add_device(self, key: str, description: str, mac_address: str, 
                  device_type: str, scan_filter: dict) -> dict:
        """Add a new device to configuration"""
        if self.get_device_by_key(key):
            raise ValueError(f"Device with key '{key}' already exists")
            
        device = {
            "key": key,
            "description": description,
            "mac_address": mac_address,
            "device_type": device_type,
            "scan_filter": scan_filter,
            "decoder": {},
            "fields": {}
        }
        self.config['devices'].append(device)
        self.save_config()
        return device

    def add_field(self, key: str, field_name: str, source_field: str, 
                 description: str, enabled: bool = True):
        """Add a field mapping to a device"""
        device = self.get_device_by_key(key)
        if device:
            device['fields'][field_name] = {
                "source_field": source_field,
                "enabled": enabled,
                "description": description
            }
            self.save_config()

class BLELogger:
    def __init__(self):
        self.config = DeviceConfig()
        self.data_file = f'ble_data_{datetime.now().strftime("%Y%m%d")}.csv'
        self.setup_logging()
        self._last_log_time = 0
        
    def setup_logging(self):
        """Setup rotating log handler"""
        self.logger = logging.getLogger('BLELogger')
        self.logger.setLevel(logging.INFO)
        handler = RotatingFileHandler('ble_logger.log', maxBytes=1024*1024, backupCount=5)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def matches_filter(self, device_name: str, scan_filter: dict) -> bool:
        """Check if device matches scan filter"""
        if 'name_pattern' in scan_filter:
            pattern = scan_filter['name_pattern']
            return bool(re.match(pattern, device_name)) if device_name else False
        return False

    async def scan_devices(self, name_pattern: Optional[str] = None) -> list:
        """Scan for BLE devices with optional name pattern filter"""
        try:
            self.logger.info(f"Starting BLE scan with filter: {name_pattern}")
            devices = await BleakScanner.discover(timeout=10)
            matching_devices = []
            
            for device in devices:
                if device.name and (name_pattern is None or 
                                  re.match(name_pattern, device.name)):
                    matching_devices.append({
                        'mac': device.address,
                        'name': device.name,
                        'rssi': device.rssi
                    })
                    self.logger.info(f"Found device: {device.name} ({device.address})")
            
            return matching_devices
        except Exception as e:
            self.logger.error(f"Scan error: {str(e)}")
            return []

    async def configure_device(self, name_pattern: Optional[str] = None):
        """Interactive device configuration"""
        # Scan for devices
        devices = await self.scan_devices(name_pattern)
        if not devices:
            print("No matching devices found")
            return

        # Device selection
        print("\nAvailable devices:")
        for i, device in enumerate(devices):
            print(f"{i+1}. {device['name']} (MAC: {device['mac']}, RSSI: {device['rssi']})")

        selection = int(input("\nSelect device number: ")) - 1
        if not (0 <= selection < len(devices)):
            print("Invalid selection")
            return

        selected_device = devices[selection]

        # Get device configuration from user
        print("\nDevice Configuration:")
        key = input("Enter unique device key (required): ").strip()
        if not key:
            print("Error: Device key is required")
            return

        description = input("Enter device description: ").strip()
        device_type = input("Enter device type: ").strip()
        
        # Configure scan filter
        scan_filter = {
            "name_pattern": input("Enter device name pattern (e.g., Govee_.*): ").strip()
        }

        # Add device to configuration
        try:
            device = self.config.add_device(
                key=key,
                description=description,
                mac_address=selected_device['mac'],
                device_type=device_type,
                scan_filter=scan_filter
            )
        except ValueError as e:
            print(f"Error: {str(e)}")
            return

        # Field configuration
        print("\nField Configuration:")
        while True:
            field_name = input("\nEnter field name (or press Enter to finish): ").strip()
            if not field_name:
                break
                
            source_field = input("Enter source field name: ").strip()
            description = input("Enter field description: ").strip()
            enabled = input("Enable field? (y/n): ").lower() == 'y'
            
            self.config.add_field(
                key=key,
                field_name=field_name,
                source_field=source_field,
                description=description,
                enabled=enabled
            )

        print("\nDevice configuration complete!")

    def decode_data(self, device_config: dict, advertisement_data: Dict) -> Optional[Dict]:
        """Decode device data based on configuration"""
        decoder_type = device_config.get('decoder', {}).get('type')
        
        if decoder_type == 'govee_h5074':
            return self._decode_govee_h5074(advertisement_data)
        # Add more decoders as needed
        
        return None

    def _decode_govee_h5074(self, advertisement_data: Dict) -> Optional[Dict]:
        """Decode Govee H5074 data"""
        try:
            if 60552 not in advertisement_data.manufacturer_data:
                return None
                
            data = advertisement_data.manufacturer_data[60552]
            if len(data) < 6:
                return None
                
            return {
                'temperature': int.from_bytes(data[1:3], byteorder='little') / 100.0,
                'humidity': int.from_bytes(data[3:5], byteorder='little') / 100.0,
                'battery': data[5],
                'raw_hex': data.hex()
            }
        except Exception as e:
            self.logger.error(f"Error decoding Govee data: {str(e)}")
            return None

    def map_data_to_config(self, device_config: dict, raw_data: Dict) -> Dict:
        """Map raw data to configured fields"""
        mapped_data = {
            'key': device_config['key'],
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        for field_name, field_config in device_config['fields'].items():
            if field_config['enabled']:
                source = field_config['source_field']
                if source in raw_data:
                    mapped_data[field_name] = raw_data[source]

        return mapped_data

    def log_data(self, data: Dict):
        """Log mapped sensor data to CSV"""
        try:
            file_exists = os.path.exists(self.data_file)
            with open(self.data_file, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=list(data.keys()))
                if not file_exists:
                    writer.writeheader()
                writer.writerow(data)
            self.logger.info(f"Data logged for device {data['key']}")
        except Exception as e:
            self.logger.error(f"Error logging data: {str(e)}")

    async def monitor_devices(self, interval: int = 60):
        """Monitor all configured devices"""
        self._last_log_time = 0  # Initialize to 0 to ensure first reading is captured
        
        def should_log() -> bool:
            current_time = time.time()
            if self._last_log_time == 0 or (current_time - self._last_log_time) >= interval:
                self._last_log_time = current_time
                return True
            return False

        def detection_callback(device, advertisement_data):
            # Only process devices in our config
            device_config = self.config.get_device_by_mac(device.address)
            if not device_config:
                return

            if not should_log():
                return

            if advertisement_data.manufacturer_data:
                raw_data = self.decode_data(device_config, advertisement_data)
                if raw_data:
                    mapped_data = self.map_data_to_config(device_config, raw_data)
                    if mapped_data:
                        self.log_data(mapped_data)
                        # Clean, minimal output showing only the sensor readings
                        print(f"\n{mapped_data['timestamp']} - {device_config['key']}")
                        for key, value in mapped_data.items():
                            if key not in ['timestamp', 'key']:
                                print(f"{key}: {value}")

        print(f"\nStarting BLE device monitoring (logging interval: {interval}s)")
        print("Press Ctrl+C to stop\n")
        
        async with BleakScanner(detection_callback=detection_callback):
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                print("\nMonitoring stopped by user")

        def detection_callback(device, advertisement_data):
            # Only process devices in our config
            device_config = self.config.get_device_by_mac(device.address)
            if not device_config:
                return

            if not should_log():
                return

            if advertisement_data.manufacturer_data:
                raw_data = self.decode_data(device_config, advertisement_data)
                if raw_data:
                    mapped_data = self.map_data_to_config(device_config, raw_data)
                    if mapped_data:
                        self.log_data(mapped_data)
                        # Clean, minimal output showing only the sensor readings
                        print(f"\n{mapped_data['timestamp']} - {device_config['key']}")
                        for key, value in mapped_data.items():
                            if key not in ['timestamp', 'key']:
                                print(f"{key}: {value}")

            # Find matching device in config
            device_config = self.config.get_device_by_mac(device.address)
            if not device_config:
                print(f"Device {device.address} not found in config")
                return

            # Verify device name matches filter
            if not self.matches_filter(device.name, device_config['scan_filter']):
                return

            if advertisement_data.manufacturer_data:
                raw_data = self.decode_data(device_config, advertisement_data)
                if raw_data:
                    mapped_data = self.map_data_to_config(device_config, raw_data)
                    if mapped_data:
                        self.log_data(mapped_data)
                        print(f"\nDevice: {device_config['key']} ({device_config['description']})")
                        for key, value in mapped_data.items():
                            if key not in ['timestamp', 'key']:
                                print(f"{key}: {value}")
                        print(f"Next update in {interval} seconds")
                        print("-" * 40)

        print(f"\nStarting monitoring with {interval} second intervals")
        print("Press Ctrl+C to stop\n")
        
        async with BleakScanner(detection_callback=detection_callback):
            self.logger.info("Started monitoring configured devices")
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                print("\nMonitoring stopped by user")

async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Generic BLE Device Logger')
    parser.add_argument('--scan', action='store_true', help='Scan for available devices')
    parser.add_argument('--name-pattern', type=str, help='Filter devices by name pattern')
    parser.add_argument('--configure', action='store_true', help='Configure a new device')
    parser.add_argument('--monitor', action='store_true', help='Monitor configured devices')
    parser.add_argument('--interval', type=int, default=60, help='Reading interval in seconds')
    
    args = parser.parse_args()
    logger = BLELogger()
    
    if args.scan:
        devices = await logger.scan_devices(args.name_pattern)
        if not devices:
            print("No matching devices found")
            return
            
        print("\nFound devices:")
        for i, device in enumerate(devices):
            print(f"{i+1}. {device['name']} (MAC: {device['mac']}, RSSI: {device['rssi']})")
    
    elif args.configure:
        await logger.configure_device(args.name_pattern)
    
    elif args.monitor:
        try:
            await logger.monitor_devices(args.interval)
        except KeyboardInterrupt:
            print("\nStopping monitoring")

if __name__ == "__main__":
    asyncio.run(main())
