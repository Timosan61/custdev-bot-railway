#!/bin/bash
cd /home/coder/Desktop/2202/Cusdev2.0/custdev-bot
nohup python3 -m src.main > bot_runtime.log 2>&1 &
echo "Бот запущен в фоновом режиме с PID: $!"
echo "Логи: tail -f bot_runtime.log"