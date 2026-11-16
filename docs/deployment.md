# Deploying to Google Cloud Run (free tier)

You do these steps with your own Google account. The repository never stores keys: GitHub Actions authenticates with
Workload Identity Federation and the secrets live in Secret Manager.

1. Create a project at <https://console.cloud.google.com> and enable billing. Cloud Run has a monthly free tier, but it
   requires a billing account. **Create a USD 1 budget alert** (Billing → Budgets & alerts) so you find out if anything
   starts costing money.
2. In Cloud Shell (the `>_` icon in the console), with your project:

   ```bash
   PROJECT_ID=your-project
   REPO=COMPUMAX-EC/caja-ahorro-api
   gcloud config set project $PROJECT_ID
   gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com iamcredentials.googleapis.com

   # Application secrets (type the values yourself; never paste them into any chat)
   openssl rand -base64 48 | gcloud secrets create caja-jwt-secret --data-file=-
   read -s -p "Treasurer password: " CLAVE && printf %s "$CLAVE" | gcloud secrets create caja-tesorero-clave --data-file=-

   # Service account GitHub Actions uses to deploy
   gcloud iam service-accounts create github-deploy
   SA=github-deploy@$PROJECT_ID.iam.gserviceaccount.com
   for ROL in roles/run.admin roles/cloudbuild.builds.editor roles/artifactregistry.admin roles/storage.admin roles/iam.serviceAccountUser roles/secretmanager.secretAccessor; do
     gcloud projects add-iam-policy-binding $PROJECT_ID --member=serviceAccount:$SA --role=$ROL
   done
   # Cloud Run uses the default Compute service account: it must be able to read the secrets
   NUM=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
   gcloud projects add-iam-policy-binding $PROJECT_ID --member=serviceAccount:$NUM-compute@developer.gserviceaccount.com --role=roles/secretmanager.secretAccessor

   # Identity federation: only this repository can use the service account
   gcloud iam workload-identity-pools create github --location=global
   gcloud iam workload-identity-pools providers create-oidc github --location=global --workload-identity-pool=github \
     --issuer-uri=https://token.actions.githubusercontent.com \
     --attribute-mapping=google.subject=assertion.sub,attribute.repository=assertion.repository \
     --attribute-condition="assertion.repository=='$REPO'"
   gcloud iam service-accounts add-iam-policy-binding $SA --role=roles/iam.workloadIdentityUser \
     --member="principalSet://iam.googleapis.com/projects/$NUM/locations/global/workloadIdentityPools/github/attribute.repository/$REPO"
   echo "Provider: projects/$NUM/locations/global/workloadIdentityPools/github/providers/github"
   ```

3. In GitHub (Settings → Secrets and variables → Actions) add:
   - variables `GCP_PROJECT_ID` (your project) and `GCP_REGION` (`us-central1`);
   - secrets `GCP_WORKLOAD_IDENTITY_PROVIDER` (the provider printed by the previous step) and `GCP_SERVICE_ACCOUNT` (`github-deploy@your-project.iam.gserviceaccount.com`).
4. The next push to `main` that passes CI deploys automatically. You can also run it by hand in Actions → *Deploy a Cloud Run*.

**Demo limitation:** the database is SQLite inside the container, so it is wiped whenever Cloud Run restarts the
instance. Real data would need Cloud SQL (PostgreSQL), which is not free.
