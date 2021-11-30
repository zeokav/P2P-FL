#!/bin/bash

rm -rf "/demo/out/${NODE_ID}/"
mkdir -p "/demo/out/${NODE_ID}"

if [[ $NODE_ID -eq 1 ]]
then
  python3 /home/work/server.py &
  python3 -u ./fl_peer.py "${SELF_IP}" 8000
else
  (( sleeptime=NODE_ID*5 ))
  sleep "$sleeptime"
  python3 -u ./fl_peer.py "${SELF_IP}" 8000 172.20.0.2:8000
fi

