# Istaroth Helm Chart

This Helm chart deploys the Istaroth web application on a Kubernetes cluster.

## Configuration

See `values.yaml` for all configurable parameters and their default values.

## Secrets Management

This chart requires SealedSecrets for managing sensitive data. You must create SealedSecrets before installing the chart.

**Prerequisites:**
- SealedSecrets controller installed in your cluster
- `kubeseal` CLI tool for creating sealed secrets

### Application Secrets

Create a SealedSecret named `<release-name>-secret` containing API keys:

```bash
kubectl create secret generic <release-name>-secret \
  --from-literal=LANGSMITH_API_KEY="..." \
  --from-literal=LANGSMITH_PROJECT="..." \
  --from-literal=LANGSMITH_TRACING="true" \
  --from-literal=GOOGLE_API_KEY="..." \
  --from-literal=CO_API_KEY="..." \
  --from-literal=OPENAI_API_KEY="..." \
  --namespace=<your-namespace> \
  --dry-run=client -o yaml | \
kubeseal -o yaml > app-secret-sealed.yaml
```

### Applying Secrets

Apply the SealedSecret before installing the chart:

```bash
kubectl apply -f app-secret-sealed.yaml
helm install <release-name> . -n <your-namespace>
```

## Database

The application requires a PostgreSQL database connection configured via the `ISTAROTH_DATABASE_URI` environment variable.

### Database Configuration

Configure the database URI in values.yaml using one of these approaches:

#### Option 1: Direct Value (Not Recommended for Production)
```yaml
backend:
  env:
    - name: ISTAROTH_DATABASE_URI
      value: "postgresql://user:password@host:5432/database"
```

#### Option 2: From Secret (Recommended)
```yaml
backend:
  env:
    - name: ISTAROTH_DATABASE_URI
      valueFrom:
        secretKeyRef:
          name: db-credentials
          key: database-uri
```

Create the secret:
```bash
kubectl create secret generic db-credentials \
  --from-literal=database-uri="postgresql://user:password@host:5432/database" \
  --namespace=<your-namespace>
```

### Environment Variables

The backend supports flexible environment variable configuration. You can use:
- Direct values: `value: "some-value"`
- Secret references: `valueFrom.secretKeyRef`
- ConfigMap references: `valueFrom.configMapKeyRef`
- Field references: `valueFrom.fieldRef`

Example configuration:
```yaml
backend:
  env:
    - name: ISTAROTH_DATABASE_URI
      valueFrom:
        secretKeyRef:
          name: db-credentials
          key: database-uri
    - name: ISTAROTH_AVAILABLE_MODELS
      value: "all"
    - name: API_KEY
      valueFrom:
        secretKeyRef:
          name: api-keys
          key: openai-key
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
