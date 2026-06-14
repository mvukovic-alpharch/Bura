#!/bin/bash
# Bura cron wrappers. Make executable: chmod +x scripts/*.sh
# crontab -e (as user bura):
#   */5  * * * *  /home/bura/bura/scripts/poll_benchmark.sh >> /home/bura/bura/logs/poll.log 2>&1
#   */12 * * * *  /home/bura/bura/scripts/poll_periphery.sh >> /home/bura/bura/logs/poll.log 2>&1
#   */30 * * * *  /home/bura/bura/scripts/close_capture.sh  >> /home/bura/bura/logs/close.log 2>&1
echo "see comments — install individual scripts below"
