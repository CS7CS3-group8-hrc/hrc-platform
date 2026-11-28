#!/usr/bin/env bash
# Sends a little traffic every second so the Grafana graphs have something to show. Ctrl+C to stop.
echo "Sending traffic... (Ctrl+C to stop)"
while true; do
  for port in 8101 8102 8103 8104 8105 8106 8107; do
    curl -s -o /dev/null --max-time 5 -X POST -d hello "http://localhost:$port"
  done
  sleep 1
done
