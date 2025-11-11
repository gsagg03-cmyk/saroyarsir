#!/bin/bash

# Force restart script - kills all gunicorn processes and cleans up PID file

echo "=========================================="
echo "FORCE RESTARTING VPS SERVICE"
echo "=========================================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "\n${YELLOW}1. Stopping systemd service...${NC}"
sudo systemctl stop saro.service

echo -e "\n${YELLOW}2. Killing ALL gunicorn processes...${NC}"
sudo pkill -9 gunicorn
sleep 2
sudo pkill -9 -f "python.*app.py"
sleep 1

echo -e "\n${YELLOW}3. Removing stale PID file...${NC}"
sudo rm -f /tmp/smartgarden-hub.pid
ls -la /tmp/smartgarden-hub.pid 2>/dev/null && echo "PID file still exists!" || echo "✓ PID file removed"

echo -e "\n${YELLOW}4. Checking for remaining processes...${NC}"
ps aux | grep -E "gunicorn|app.py" | grep -v grep || echo "✓ No gunicorn processes running"

echo -e "\n${YELLOW}5. Starting service...${NC}"
sudo systemctl start saro.service
sleep 3

echo -e "\n${YELLOW}6. Checking service status...${NC}"
if sudo systemctl is-active --quiet saro.service; then
    echo -e "${GREEN}✓ Service started successfully!${NC}"
    sudo systemctl status saro.service --no-pager -l | head -20
else
    echo -e "${RED}✗ Service failed to start${NC}"
    echo -e "\nRecent logs:"
    sudo journalctl -u saro.service -n 20 --no-pager
    exit 1
fi

echo -e "\n${GREEN}=========================================="
echo -e "SERVICE RESTARTED SUCCESSFULLY!"
echo -e "==========================================${NC}"
