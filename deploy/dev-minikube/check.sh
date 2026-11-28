#!/usr/bin/env bash
# Sends hello to both Kafka agents from inside the cluster and shows the Kafka hand-offs in the logs.
set -euo pipefail
for svc in ambulance-coordination-agent patient-transfer-agent; do
  kubectl -n hrc run "hello-$svc" --rm -i --restart=Never --image=curlimages/curl --quiet -- \
    curl -s -X POST -d hello "http://$svc:8080"; echo
done
sleep 3
echo "--- allocation-coordinator log:"; kubectl -n hrc logs deploy/allocation-coordinator | grep -E 'CONSUMED|produced' | tail -6
echo "--- ambulance agent log:";        kubectl -n hrc logs deploy/ambulance-coordination-agent | grep -E 'CONSUMED|produced' | tail -4
