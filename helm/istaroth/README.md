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

The following table lists the configurable parameters and their default values.

### Global Settings

| Parameter | Description | Default |
|-----------|-------------|---------|
| `replicaCount` | Number of replicas | `1` |

### Backend Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `backend.image.repository` | Backend image repository | `isundaylee/istaroth` |
| `backend.image.tag` | Backend image tag | `latest` |
| `backend.image.pullPolicy` | Image pull policy | `Always` |
| `backend.service.type` | Service type | `ClusterIP` |
| `backend.service.port` | Service port | `5000` |
| `backend.resources.limits.cpu` | CPU limit | `2000m` |
| `backend.resources.limits.memory` | Memory limit | `4Gi` |
| `backend.resources.requests.cpu` | CPU request | `500m` |
| `backend.resources.requests.memory` | Memory request | `1Gi` |

### Frontend Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `frontend.image.repository` | Frontend image repository | `isundaylee/istaroth-frontend` |
| `frontend.image.tag` | Frontend image tag | `latest` |
| `frontend.image.pullPolicy` | Image pull policy | `Always` |
| `frontend.service.type` | Service type | `ClusterIP` |
| `frontend.service.port` | Service port | `80` |
| `frontend.resources.limits.cpu` | CPU limit | `500m` |
| `frontend.resources.limits.memory` | Memory limit | `512Mi` |
| `frontend.resources.requests.cpu` | CPU request | `100m` |
| `frontend.resources.requests.memory` | Memory request | `128Mi` |

### Persistence

| Parameter | Description | Default |
|-----------|-------------|---------|
| `persistence.enabled` | Enable persistent storage | `true` |
| `persistence.storageClass` | Storage class name | `""` (default) |
| `persistence.accessMode` | Access mode | `ReadWriteOnce` |
| `persistence.size` | Storage size | `10Gi` |

### Ingress

| Parameter | Description | Default |
|-----------|-------------|---------|
| `ingress.enabled` | Enable ingress | `false` |
| `ingress.className` | Ingress class name | `nginx` |
| `ingress.hosts[0].host` | Hostname | `istaroth.example.com` |
| `ingress.tls` | TLS configuration | `[]` |

## Persistence

The chart mounts a persistent volume to store:
- SQLite database at `/data/database/web.sqlite`
- Checkpoint data at `/data/checkpoint`
- HuggingFace models at `/data/models/hf`

## Environment Variables

### Backend Environment Variables

Set these in `backend.env`:
```yaml
backend:
  env:
    LANGSMITH_API_KEY: "your-api-key"
    LANGCHAIN_PROJECT: "istaroth-rag"
    LANGCHAIN_TRACING_V2: "true"
```

### Frontend Environment Variables

Set these in `frontend.env`:
```yaml
frontend:
  env:
    VITE_API_BASE_URL: "http://backend:5000"
```

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
