# Despliegue en Google Cloud Run (capa gratuita)

Estos pasos los haces tú, con tu cuenta de Google. El repositorio nunca guarda llaves: GitHub Actions se autentica con
Workload Identity Federation y los secretos viven en Secret Manager.

1. Crea un proyecto en <https://console.cloud.google.com> y activa la facturación. Cloud Run tiene una capa gratuita
   mensual, pero pide una cuenta de facturación. **Crea una alerta de presupuesto de USD 1** (Facturación → Presupuestos y
   alertas) para enterarte si algo empieza a cobrar.
2. En Cloud Shell (el ícono `>_` de la consola), con tu proyecto:

   ```bash
   PROJECT_ID=tu-proyecto
   REPO=COMPUMAX-EC/caja-ahorro-api
   gcloud config set project $PROJECT_ID
   gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com iamcredentials.googleapis.com

   # Secretos de la aplicación (escribe tú los valores; no los pegues en ningún chat)
   openssl rand -base64 48 | gcloud secrets create caja-jwt-secret --data-file=-
   read -s -p "Clave del tesorero: " CLAVE && printf %s "$CLAVE" | gcloud secrets create caja-tesorero-clave --data-file=-

   # Cuenta de servicio que usa GitHub Actions para desplegar
   gcloud iam service-accounts create github-deploy
   SA=github-deploy@$PROJECT_ID.iam.gserviceaccount.com
   for ROL in roles/run.admin roles/cloudbuild.builds.editor roles/artifactregistry.admin roles/storage.admin roles/iam.serviceAccountUser roles/secretmanager.secretAccessor; do
     gcloud projects add-iam-policy-binding $PROJECT_ID --member=serviceAccount:$SA --role=$ROL
   done
   # Cloud Run usa la cuenta de servicio de Compute por defecto: debe poder leer los secretos
   NUM=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
   gcloud projects add-iam-policy-binding $PROJECT_ID --member=serviceAccount:$NUM-compute@developer.gserviceaccount.com --role=roles/secretmanager.secretAccessor

   # Federación de identidad: solo este repositorio puede usar la cuenta de servicio
   gcloud iam workload-identity-pools create github --location=global
   gcloud iam workload-identity-pools providers create-oidc github --location=global --workload-identity-pool=github \
     --issuer-uri=https://token.actions.githubusercontent.com \
     --attribute-mapping=google.subject=assertion.sub,attribute.repository=assertion.repository \
     --attribute-condition="assertion.repository=='$REPO'"
   gcloud iam service-accounts add-iam-policy-binding $SA --role=roles/iam.workloadIdentityUser \
     --member="principalSet://iam.googleapis.com/projects/$NUM/locations/global/workloadIdentityPools/github/attribute.repository/$REPO"
   echo "Proveedor: projects/$NUM/locations/global/workloadIdentityPools/github/providers/github"
   ```

3. En GitHub (Settings → Secrets and variables → Actions) agrega:
   - variables `GCP_PROJECT_ID` (tu proyecto) y `GCP_REGION` (`us-central1`);
   - secrets `GCP_WORKLOAD_IDENTITY_PROVIDER` (el proveedor que imprimió el paso anterior) y `GCP_SERVICE_ACCOUNT` (`github-deploy@tu-proyecto.iam.gserviceaccount.com`).
4. El siguiente push a `main` que pase CI se despliega solo. También puedes correrlo a mano en Actions → *Deploy a Cloud Run*.

**Limitación de la demo:** la base es SQLite dentro del contenedor, así que se borra cuando Cloud Run reinicia la
instancia. Para datos reales haría falta Cloud SQL (PostgreSQL), que no es gratuito.
