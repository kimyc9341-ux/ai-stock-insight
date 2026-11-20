#!/bin/bash
# run_auto.sh - 백그라운드 자동 실행 스크립트
echo "[+] Starting AI Stock Auto Monitor in background..."
nohup ~/miniconda3/envs/antigravity/bin/python /mnt/c/Users/통신운용/Desktop/agent/auto_monitor.py > /mnt/c/Users/통신운용/Desktop/agent/logs/monitor.log 2>&1 &
echo "[+] Auto Monitor started! PID: $!"
echo "[+] View live logs with: tail -f /mnt/c/Users/통신운용/Desktop/agent/logs/monitor.log"