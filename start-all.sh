cd ~/BLOOM
./bloom_daemon.sh > logs/app.log 2>&1 &
echo $! > logs/app.pid
