# Istaroth Helm Chart

This Helm chart deploys the Istaroth web application on a Kubernetes cluster.

## Configuration

See `values.yaml` for all configurable parameters and their default values.

### Secrets Management

This chart requires SealedSecrets for managing sensitive data. You must create a SealedSecret before installing the chart.

**Prerequisites:**
- SealedSecrets controller installed in your cluster
- `kubeseal` CLI tool for creating sealed secrets

**Steps:**
1. Create a SealedSecret with your sensitive data:
   ```bash
   kubectl create secret generic myapp-secret \
     --from-literal=LANGSMITH_API_KEY="..." \
     --from-literal=LANGSMITH_PROJECT="..." \
     --from-literal=LANGSMITH_TRACING="true" \
     --from-literal=GOOGLE_API_KEY="..." \
     --from-literal=CO_API_KEY="..." \
     --from-literal=OPENAI_API_KEY="..." \
     --dry-run=client -o yaml | \
   kubeseal -o yaml > myapp-secret-sealed.yaml
   ```

2. Edit the SealedSecret to use the correct secret name:
   ```yaml
   apiVersion: bitnami.com/v1alpha1
   kind: SealedSecret
   metadata:
     name: myapp-sealed-secret
     namespace: target-namespace
   spec:
     encryptedData:
      ...
     template:
       metadata:
         name: myapp-secret  # Must match {release-name}-secret
         labels:
           app.kubernetes.io/name: myapp
           app.kubernetes.io/instance: myapp
   ```

3. Apply the SealedSecret before installing the chart:
   ```bash
   kubectl apply -f myapp-sealed-secret.yaml
   helm install myapp . -n target-namespace
   ```

## Database

The chart uses PostgreSQL as the database backend:

### PostgreSQL Configuration
- Uses a separate persistent volume for database storage
- Configurable database name, username, and password
- Automatic database initialization
- Health checks with `pg_isready`
- PostgreSQL 15 by default

### Database Configuration
```yaml
postgres:
  database: istaroth
  username: istaroth
  password: changeme  # IMPORTANT: Change in production!
  persistence:
    size: 5Gi
    storageClass: ""  # Uses default storage class
```

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
