#!/usr/bin/env bash
# Installs / upgrades Prometheus + Grafana (kube-prometheus-stack) into the "monitoring" namespace.
#   deploy/monitoring/install.sh [minikube|eks]      (default: minikube)
#   CHART_VERSION=<x.y.z> deploy/monitoring/install.sh   pins the chart version (recommended once it works)
set -euo pipefail
cd "$(dirname "$0")"
ENV_NAME="${1:-minikube}"

[ -f ../../.env ] && { set -a; . ../../.env; set +a; }
: "${GRAFANA_ADMIN_PASSWORD:?Set GRAFANA_ADMIN_PASSWORD (in .env at the repo root, or in your shell)}"

echo "Cluster: $(kubectl config current-context)   Environment: $ENV_NAME"
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null 2>&1 || true
helm repo update

kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -
# The password is created in the cluster from your environment, so it never lands in a file in git.
kubectl -n monitoring create secret generic grafana-admin \
  --from-literal=admin-user=admin --from-literal=admin-password="$GRAFANA_ADMIN_PASSWORD" \
  --dry-run=client -o yaml | kubectl apply -f -

helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring ${CHART_VERSION:+--version "$CHART_VERSION"} \
  -f values.yaml -f "values-${ENV_NAME}.yaml" --wait --timeout 10m

echo
helm list -n monitoring     # note the CHART column: pin it with CHART_VERSION=... next time
cat <<MSG

Open Grafana:     kubectl -n monitoring port-forward svc/monitoring-grafana 3000:80      -> http://localhost:3000  (admin / your password)
Open Prometheus:  kubectl -n monitoring port-forward svc/monitoring-kube-prometheus-prometheus 9090:9090   -> http://localhost:9090
(If a service name is not found: kubectl -n monitoring get svc)
MSG
