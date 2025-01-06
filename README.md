# Bluetooth Sensor Temperature Logging

A Python-based solution for logging temperature and humidity data from Govee H5074 Bluetooth sensors. This project is designed to run on Debian 10 ARM platforms (tested on an Amplifed Engineering nodeG5 IMX8PLUS gateway).

Device vendor : www.amplified.com.au

## Prerequisites

```bash
# System dependencies
sudo apt-get update
sudo apt-get install python3-pip bluetooth bluez libbluetooth-dev libglib2.0-dev

# Python packages
pip3 install bleak
```

## Usage

The script provides several commands for device management and data logging:

### 1. Scanning for Devices

To scan for available Govee sensors:

```bash
python logger.py --scan --name-pattern "Govee_H5074"
```

### 2. Device Configuration

Configure a new device by scanning and selecting from available devices:

```bash
python logger.py --configure
```

Example output:
```
Found devices:
1. Govee_H5074_6665 (MAC: A4:C1:38:9F:66:65, RSSI: -63)

Select device number to configure: 1
Device configured: Govee_H5074_6665
```

This will create a device_config.json file with the device details:
```json
{
    "devices": [
        {
            "key": "H5074_office",
            "description": "Govee BT temp and humidity sensor for office",
            "mac_address": "A4:C1:38:9F:66:65",
            "device_type": "Sensor",
            "scan_filter": {
                "name_pattern": "Govee_H5074"
            },
            "decoder": {
                "type": "govee_h5074",
                "manufacturer_id": 60552
            },
            "fields": {
                "temperature": {
                    "source_field": "temperature",
                    "enabled": true,
                    "description": "temperature measured"
                },
                "humidity": {
                    "source_field": "humidity",
                    "enabled": true,
                    "description": "humidity measured"
                }
            }
        }
    ]
}
```

### 3. Continuous Monitoring

To start monitoring configured devices:

```bash
python logger.py --monitor --interval 15
```

This will:
- Read data from all configured devices every 15 seconds
- Log temperature and humidity readings to a CSV file
- Create a new log file each day (format: ble_data_YYYYMMDD.csv)

## Command Line Options

```
usage: logger.py [-h] [--scan] [--name-pattern NAME_PATTERN] [--configure] [--monitor] [--interval INTERVAL]

Generic BLE Device Logger

optional arguments:
  -h, --help            show this help message and exit
  --scan                Scan for available devices
  --name-pattern NAME_PATTERN
                        Filter devices by name pattern
  --configure           Configure a new device
  --monitor            Monitor configured devices
  --interval INTERVAL   Reading interval in seconds
```

## Output Format

The script generates daily CSV files with the following format:
- Filename: ble_data_YYYYMMDD.csv
- Fields: timestamp, device_key, temperature, humidity

## Notes

- Requires sudo privileges or appropriate Bluetooth permissions
- Designed for Govee H5074 sensors but can be extended for other BLE devices
- Uses Bleak library for robust Bluetooth communication
