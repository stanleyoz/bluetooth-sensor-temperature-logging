#!/usr/bin/env python3

import asyncio
import struct
from bleak import BleakScanner
from datetime import datetime
import csv
import logging
from logging.handlers import RotatingFileHandler

class GoveeSensor:
    def __init__(self, mac_address):
        self.mac_address = mac_address.upper()
        self.data_file = f'govee_data_{datetime.now().strftime("%Y%m%d")}.csv'
        self.setup_logging()
        
    def setup_logging(self):
        self.logger = logging.getLogger('GoveeSensor')
        self.logger.setLevel(logging.DEBUG)
        handler = RotatingFileHandler('govee_sensor.log', maxBytes=1024*1024, backupCount=5)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def decode_sensor_data(self, manufacturer_data):
        """Decode Govee H5074 manufacturer specific data"""
        try:
            # Manufacturer ID 60552 contains our sensor data
            if 60552 not in manufacturer_data:
                return None
                
            data = manufacturer_data[60552]
            self.logger.debug(f"Raw manufacturer data: {data.hex()}")
            
            # Data format: b'\x00F\x0c\x88\x0eE\x02'
            # Looking at your data:
            # Temperature bytes: [1:3] = 46 0c = 3142 (12.46°C)
            # Humidity bytes: [3:5] = 88 0e = 3720 (37.20%)
            # Battery might be at position 5 = 45 (69%)
            
            if len(data) < 6:
                return None
                
            # Extract values (adjusting positions based on observed data)
            temp = int.from_bytes(data[1:3], byteorder='little') / 100.0
            humidity = int.from_bytes(data[3:5], byteorder='little') / 100.0
            battery = data[5]  # Single byte for battery percentage
            
            decoded_data = {
                'temperature': temp,
                'humidity': humidity,
                'battery': battery,
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'raw_hex': data.hex()  # Include raw data for debugging
            }
            
            self.logger.debug(f"Decoded data: {decoded_data}")
            return decoded_data
            
        except Exception as e:
            self.logger.error(f"Error decoding sensor data: {str(e)}")
            return None

    def log_data(self, data):
        """Log sensor data to CSV"""
        try:
            with open(self.data_file, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['timestamp', 'temperature', 'humidity', 'battery', 'raw_hex'])
                if f.tell() == 0:  # File is empty
                    writer.writeheader()
                writer.writerow(data)
            self.logger.info(f"Data logged: Temp={data['temperature']}°C, Humidity={data['humidity']}%, Battery={data['battery']}%")
        except Exception as e:
            self.logger.error(f"Error logging data: {str(e)}")

    async def scan_advertisements(self):
        """Scan for advertisements from the configured device"""
        def detection_callback(device, advertisement_data):
            if device.address.upper() == self.mac_address:
                if advertisement_data.manufacturer_data:
                    self.logger.debug(f"Raw advertisement data: {advertisement_data}")
                    data = self.decode_sensor_data(advertisement_data.manufacturer_data)
                    if data:
                        self.log_data(data)
                        print(f"\nTemperature: {data['temperature']}°C")
                        print(f"Humidity: {data['humidity']}%")
                        print(f"Battery: {data['battery']}%")
                        print(f"Raw data: {data['raw_hex']}")
                        print("-" * 40)

        async with BleakScanner(detection_callback=detection_callback):
            print(f"Started scanning for device: {self.mac_address}")
            print("Waiting for advertisements...")
            while True:
                await asyncio.sleep(1)

async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Govee H5074 BLE Scanner')
    parser.add_argument('--mac', type=str, required=True, help='MAC address of the sensor')
    args = parser.parse_args()
    
    sensor = GoveeSensor(args.mac)
    try:
        await sensor.scan_advertisements()
    except KeyboardInterrupt:
        print("\nStopping scanner")

if __name__ == "__main__":
    asyncio.run(main())
