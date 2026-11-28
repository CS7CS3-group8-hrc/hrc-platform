#!/usr/bin/env bash
# Builds the 7 service images INTO minikube (no registry needed), then deploys Kafka + the services.
# Run from anywhere:  deploy/dev-minikube/run.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
SERVICES="allocation-coordinator patient-transfer-agent emergency-coordination-agent ambulance-coordination-agent rag-service explanation-service forecasting-service"

kubectl config current-context
for s in $SERVICES; do
  echo "== building hrc/$s:dev"
  minikube image build -t "hrc/$s:dev" "services/$s"
done

kubectl apply -f deploy/dev-minikube/00-namespace.yaml
kubectl apply -f deploy/dev-minikube/10-kafka.yaml
kubectl -n hrc rollout status statefulset/kafka --timeout=240s
kubectl -n hrc wait --for=condition=complete job/kafka-init --timeout=240s
kubectl apply -f deploy/dev-minikube/20-services.yaml
for s in $SERVICES; do kubectl -n hrc rollout status "deployment/$s" --timeout=180s; done
kubectl -n hrc get pods
echo
echo "Rebuilt an image? Run: kubectl -n hrc rollout restart deployment   (same :dev tag is not re-pulled automatically)"
