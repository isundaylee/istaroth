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

### PostgreSQL Secrets

Create a SealedSecret named `<release-name>-postgres-secret` containing database credentials:

```bash
kubectl create secret generic <release-name>-postgres-secret \
  --from-literal=POSTGRES_DB="istaroth" \
  --from-literal=POSTGRES_USER="istaroth" \
  --from-literal=POSTGRES_PASSWORD="your-secure-password" \
  --namespace=<your-namespace> \
  --dry-run=client -o yaml | \
kubeseal -o yaml > postgres-secret-sealed.yaml
```

### Applying Secrets

Apply both SealedSecrets before installing the chart:

```bash
kubectl apply -f app-secret-sealed.yaml
kubectl apply -f postgres-secret-sealed.yaml
helm install <release-name> . -n <your-namespace>
```

## Database

The chart uses PostgreSQL as the database backend:

### PostgreSQL Configuration
- Uses a separate persistent volume for database storage
- Configurable database name, username, and password
- Automatic database initialization
- Health checks with `pg_isready`
- PostgreSQL 15 by default


## Persistence

The chart handles persistence with a hybrid approach:

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

### PostgreSQL Database (User-Managed)

**IMPORTANT**: You must create the PostgreSQL PVC before installing this chart.

- **Created by:** User (pre-existing PVC required)
- **Purpose:** Stores PostgreSQL database files
- **Mount path:** `/var/lib/postgresql/data`
- **Why user-managed:** Database data should survive Helm release deletion

#### Creating PostgreSQL PVC

```bash
kubectl create -f - <<EOF
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: istaroth-postgres-data
  namespace: your-namespace
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 5Gi
  # storageClassName: your-storage-class  # Optional
EOF
```

#### Configuration

Reference the PostgreSQL PVC in your values.yaml:

```yaml
postgres:
  persistence:
    existingClaim: "istaroth-postgres-data"
```

**Note**: Database credentials are managed via SealedSecret, not values.yaml.
