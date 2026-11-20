#!/usr/bin/env bash
# Send "hello" to each agent and print its reply
for port in 8101 8102 8103 8104 8105 8106; do
  curl -s -X POST -d "hello" "http://localhost:$port"; echo
done
