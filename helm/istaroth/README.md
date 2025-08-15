# Istaroth Helm Chart

This Helm chart deploys the Istaroth web application on a Kubernetes cluster.

## Prerequisites

- Kubernetes 1.19+
- Helm 3.0+
- PV provisioner support in the underlying infrastructure (for persistent storage)

## Installation

### Add the repository (if hosted)
```bash
helm repo add istaroth https://your-helm-repo-url
helm repo update
```

### Install from local directory
```bash
helm install istaroth ./helm/istaroth
```

### Install with custom values
```bash
helm install istaroth ./helm/istaroth -f custom-values.yaml
```

## Configuration

See `values.yaml` for all configurable parameters and their default values.

## Persistence

The chart mounts a persistent volume to store:
- SQLite database at `/data/database/web.sqlite`
- Checkpoint data at `/data/checkpoint`
- HuggingFace models at `/data/models/hf`


## Examples

### Deploy with external database
```yaml
# custom-values.yaml
persistence:
  enabled: true
  size: 20Gi
  storageClass: fast-ssd

backend:
  env:
    DATABASE_PATH: "/data/database/production.sqlite"
```

### Deploy with ingress
```yaml
# custom-values.yaml
ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: istaroth.yourdomain.com
      paths:
        - path: /
          pathType: Prefix
          backend: frontend
        - path: /api
          pathType: Prefix
          backend: backend
  tls:
    - secretName: istaroth-tls
      hosts:
        - istaroth.yourdomain.com
```

## Uninstallation

```bash
helm uninstall istaroth
```

## Upgrading

```bash
helm upgrade istaroth ./helm/istaroth
```

## Troubleshooting

### Check pod status
```bash
kubectl get pods -l app.kubernetes.io/instance=istaroth
```

### View logs
```bash
# Backend logs
kubectl logs -l app.kubernetes.io/name=istaroth-backend

# Frontend logs
kubectl logs -l app.kubernetes.io/name=istaroth-frontend
```

### Access the application locally
```bash
# Port-forward the frontend
kubectl port-forward svc/istaroth-frontend 8080:80

# Port-forward the backend
kubectl port-forward svc/istaroth-backend 5000:5000
```
