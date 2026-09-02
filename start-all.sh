#!/bin/bash
cd ~/BLOOM
pkill -f "bloom_daemon.sh" 2>/dev/null
pkill -f "python3" 2>/dev/null
sleep 1
mkdir -p logs
if [ -f bloom_daemon.sh ]; then
  ./bloom_daemon.sh > logs/app.log 2>&1 &
elif [ -f main.py ]; then
  python3 main.py > logs/app.log 2>&1 &
else
  echo "No main script found" > logs/app.log
fi
echo $! > logs/app.pid
echo "BLOOM started (PID $(cat logs/app.pid))"
