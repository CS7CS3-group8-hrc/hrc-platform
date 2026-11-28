# Deploying and monitoring on Kubernetes

```
deploy/
  dev-minikube/   TEST-ONLY manifests: Kafka + the 7 Python services, for trying things on minikube
  monitoring/     Helm settings + install script for Prometheus and Grafana (kube-prometheus-stack)
```

The real cluster (EKS) and its manifests are owned by the infra team. Everything here is written so
it carries over: only the small `values-<env>.yaml` file differs between minikube and EKS.

## For the infra team: what a deployment needs so monitoring picks it up

Two things on every service's pod, nothing else:

1. **A pod label:** `monitoring: hrc`
2. **A container port named `metrics`** that serves Prometheus metrics at `/metrics`
   (the Python services serve it on 9100; see `services/*/metrics.py`).

```yaml
spec:
  template:
    metadata:
      labels:
        monitoring: hrc
    spec:
      containers:
        - name: my-service
          ports:
            - {name: metrics, containerPort: 9100}
```

Separately, and with no changes to the service: **every pod in the cluster** gets CPU, memory and
restart monitoring automatically once the monitoring stack is installed.

Other things the services need from the cluster: Kafka reachable at `kafka:9092` (env `KAFKA_BOOTSTRAP`)
with topics `hrc.hello.requests` and `hrc.hello.replies`, and **no HTTP health probes on port 8080**
(any request there is treated as a message; use a TCP probe or the metrics port).

## Try it on minikube

Prerequisites: `brew install minikube kubectl helm`, then `minikube start --driver=docker --cpus=4 --memory=6144`.

**1. Deploy Kafka and the services**
```bash
deploy/dev-minikube/run.sh      # builds images into minikube, deploys everything, waits until ready
deploy/dev-minikube/check.sh    # sends hello inside the cluster; shows the Kafka hand-offs in the logs
```

**2. Install Prometheus and Grafana**
```bash
cp .env.example .env            # set GRAFANA_ADMIN_PASSWORD (never commit .env)
deploy/monitoring/install.sh
```
Then run the two `port-forward` commands it prints.

**3. Checkpoint:** in Grafana open **Dashboards, then Kubernetes / Compute Resources / Namespace (Pods)** and
choose namespace `hrc`. You should see CPU and memory for every pod, including Kafka and all 7 services.

Pin the chart version once it works: `CHART_VERSION=<version from helm list> deploy/monitoring/install.sh`.

## Troubleshooting

- **Kubelet / cAdvisor targets show `401 Unauthorized` (Prometheus, Status, Targets), and the pod dashboards are empty.**
  Older minikube setups need the kubelet to allow token authentication. Recreate the cluster with:
  `minikube delete && minikube start --driver=docker --cpus=4 --memory=6144 --extra-config=kubelet.authentication-token-webhook=true --extra-config=kubelet.authorization-mode=Webhook`
- **Pods stuck `Pending`:** not enough memory. Give Docker Desktop more (Settings, Resources) or `minikube start --memory=...`.
- **`ErrImageNeverPull`:** the image was not built into minikube. Re-run `run.sh`.
- **Start over:** `kubectl delete namespace hrc` and `helm uninstall monitoring -n monitoring`
  (the chart's CRDs stay behind; that is normal).

## Not done yet (next phases)

Phase 2: a shared PodMonitor so Prometheus collects the services' own `/metrics` (Kafka message counts etc.).
Phase 3: Kafka exporter. Phase 4: the Grafana dashboard loaded from a ConfigMap.
