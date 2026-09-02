#!/bin/bash
cd ~/BLOOM
if [ -f logs/app.pid ]; then
  kill $(cat logs/app.pid) 2>/dev/null
fi
pkill -f "bloom_daemon.sh" 2>/dev/null
pkill -f "python3" 2>/dev/null
rm -f logs/*.pid
echo "BLOOM stopped"
