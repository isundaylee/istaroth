# Istaroth Helm Chart

This Helm chart deploys the Istaroth web application on a Kubernetes cluster.

## Configuration

See `values.yaml` for all configurable parameters and their default values.

**REQUIRED**: The application requires a database connection configured via the `ISTAROTH_DATABASE_URI` environment variable in the `backend.env` section of values. The Helm chart will fail if this is not provided.

## Secrets Management

This chart requires secrets injected for managing sensitive data. One way to do this is with sealed secrets:

Create a `SealedSecret` named `<release-name>-secret` containing API keys:

```bash
kubectl create secret generic <release-name>-secret \
  --namespace=<your-namespace> \
  --from-literal=LANGSMITH_API_KEY="..." \
  --from-literal=LANGSMITH_PROJECT="..." \
  --from-literal=LANGSMITH_TRACING="true" \
  --from-literal=GOOGLE_API_KEY="..." \
  --from-literal=CO_API_KEY="..." \
  --from-literal=OPENAI_API_KEY="..." \
  --dry-run=client -o yaml | \
kubeseal -o yaml > app-secret-sealed.yaml
```

Apply the SealedSecret before installing the chart:

```bash
kubectl apply -f app-secret-sealed.yaml
helm install <release-name> . -n <your-namespace>
```

## Persistence

### Backend Application Data (Helm-Managed)
- **Created by:** Helm chart automatically
- **Purpose:** Stores checkpoint data, HuggingFace models, and other application data
- **Mount path:** `/data`
- **Configuration:** Set via `persistence.*` values

```yaml
persistence:
  storageClass: ""  # Uses default storage class
  accessMode: ReadWriteOnce
  size: 10Gi
```
