#!/bin/bash
# SmartLocker Launcher — RPi autostart script
#
# Install as systemd service:
#   sudo cp smartlocker.service /etc/systemd/system/
#   sudo systemctl enable smartlocker
#   sudo systemctl start smartlocker
#
# Or add to /etc/rc.local:
#   /home/pi/smartlocker-edge/smartlocker.sh &

cd "$(dirname "$0")"

# Activate venv if exists
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

exec python3 launcher.py "$@"
