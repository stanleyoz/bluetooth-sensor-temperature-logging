# Bluetooth Governance System for Ubuntu 20.04 on NVIDIA Jetson

This repository contains tools and scripts for managing Bluetooth connectivity on Ubuntu 20.04 systems running on NVIDIA Jetson platforms, specifically tested with Intel AX9560 WiFi/Bluetooth M.2 cards.

## System Requirements

- Ubuntu 20.04 LTS
- NVIDIA Jetson platform
- Intel AX9560 WiFi/Bluetooth M.2 card
- Python 3.8+

## Known Issues and Solutions

### Multiple Bluetooth Instance Conflicts

One common issue encountered is D-Bus conflicts when multiple Python scripts attempt to access the Bluetooth daemon simultaneously. This manifests as:

```bash
Job for bluetooth.service failed because the control process exited with error code.
```

With the following specific error in logs:
```
D-Bus setup failed: Name already in use
Unable to get on D-Bus
```

#### Resolution Steps

1. Kill existing Bluetooth processes:
```bash
sudo pkill -9 bluetoothd
sudo rm -f /var/run/bluetooth/bluetooth.pid
```

2. Restart the Bluetooth service:
```bash
sudo systemctl daemon-reload
sudo systemctl restart bluetooth
```

## Best Practices for Development

When working with this system, follow these guidelines:

1. **Resource Cleanup**: Always implement proper cleanup of Bluetooth connections:
```python
try:
    # Your Bluetooth code here
finally:
    # Cleanup code
    bluetooth_connection.close()
```

2. **Connection Management**: Use context managers when possible:
```python
with BluetoothConnection() as bt:
    # Your code here
    pass
```

3. **Error Handling**: Implement proper error handling for resource conflicts:
```python
try:
    bluetooth_connection.connect()
except DBusException as e:
    if "Name already in use" in str(e):
        # Handle resource conflict
        pass
```

## Configuration

The Bluetooth system configuration file is located at `/etc/bluetooth/main.conf`. Ensure it contains the following basic configuration:

```ini
[General]
Name = Ubuntu-BT
Class = 0x000100
DiscoverableTimeout = 0
PairableTimeout = 0
Privacy = 0
Always = true
```

## Troubleshooting

Common troubleshooting commands:

1. Check Bluetooth service status:
```bash
systemctl status bluetooth.service
```

2. View detailed logs:
```bash
journalctl -u bluetooth.service -n 50
```

3. Verify hardware detection:
```bash
lspci | grep -i bluetooth
sudo dmesg | grep -i bluetooth
```

4. Check if Bluetooth is blocked:
```bash
sudo rfkill list
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request
