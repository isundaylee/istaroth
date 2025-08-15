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

## Persistence

The chart mounts a persistent volume to store:
- SQLite database at `/data/database/web.sqlite`
- Checkpoint data at `/data/checkpoint`
- HuggingFace models at `/data/models/hf`
