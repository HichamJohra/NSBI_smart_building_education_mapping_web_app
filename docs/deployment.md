# Deployment (Docker, Google Cloud Run)

The app runs in a Docker container (`Dockerfile`, served by gunicorn: `app:server`). The dataset
(`data/smart_building_education_dataset.xlsx`) is part of the image: after changing it, commit and redeploy.
The app stores nothing on the server (selections are kept in the visitor's browser tab only).

**Live app:** <https://nsbi-smart-building-education-mapping.cloud.run>

Hosting: Google Cloud Run (region `europe-north2`, Stockholm), redeployed automatically by a Cloud Build trigger on
every push to `main`. Resources: 512 MiB, 1 CPU, 0–3 instances, request-based billing, public access.
Project identifiers and service account names are kept in the maintainer's private notes, not in this repository.

Workflow: work on `dev` → pull request `dev` → `main` → merge → Cloud Build builds and deploys automatically
(Cloud Build → History).

Security principles: two dedicated service accounts, never the Compute Engine default account:
a **runtime** account with no roles (identity of the public web app) and a **build** account with only Cloud Run
Admin, Artifact Registry Writer, Logs Writer, plus Service Account User on the runtime account.

## 1. Test the container locally (optional)

```bash
docker build -t nsbi-education-app .
docker run --rm -p 8080:8080 nsbi-education-app
# open http://localhost:8080
```

## 2. One-time Google Cloud setup

Requirements: a Google Cloud project with billing enabled, and the
[Google Cloud CLI](https://cloud.google.com/sdk/docs/install) installed on your PC.
Replace `PROJECT_ID` and `REGION` (e.g. `europe-north1`, Finland).

```bash
gcloud auth login
gcloud config set project PROJECT_ID
gcloud config set run/region REGION
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
```

## 3a. Recommended: continuous deployment from GitHub (no gcloud CLI needed)

Set up once in the Google Cloud Console: **Cloud Run → Deploy container / Create service → Continuously deploy
from a repository → Set up with Cloud Build**.

1. Repository provider GitHub: authenticate and install the *Google Cloud Build* GitHub app on the repository
   `HichamJohra/NSBI_smart_building_education_mapping_web_app`.
2. Branch: `^main$`. Build type: **Dockerfile**, source location `/Dockerfile`.
3. Service name `nsbi-smart-building-education-mapping-web-app`, region `europe-north2` (Stockholm), authentication
   **Allow public access** (unauthenticated), container port 8080, memory 512 MiB, CPU 1, minimum instances 0,
   maximum instances 3, service account = a dedicated runtime account without roles.
4. Create. Then in **Cloud Build → Triggers**, edit the generated trigger: service account = a dedicated build
   account (roles above), and in the inline YAML keep `options: logging: CLOUD_LOGGING_ONLY` (required when a
   user-managed service account runs the build). Run the trigger once.
5. The first build starts immediately (Cloud Build → History shows the progress); the URL appears on the
   service page.

Every merge into `main` (pull request from `dev`) then rebuilds and redeploys automatically, so `main` = what is
online. Pushes to `dev` do not deploy.

## 3b. Alternative: manual deploy from your PC (gcloud CLI)

From the project root, on the branch you want to publish (normally `main` after merging `dev`). The source is
uploaded (minus the files in `.gcloudignore`), Cloud Build builds the image from the `Dockerfile` and Cloud Run
starts it. The first deploy asks to create an Artifact Registry repository (`cloud-run-source-deploy`): answer yes.

```bash
gcloud run deploy nsbi-smart-building-education --source . --allow-unauthenticated --memory 512Mi --cpu 1 --min-instances 0 --max-instances 3
```

The command prints the service URL (`https://nsbi-smart-building-education-….run.app`).
`--min-instances 0` costs nothing when idle; the first visit after a pause then takes a few seconds (cold start).
Use `--memory 1Gi` if the logs show out-of-memory restarts. Logs: Cloud Console → Cloud Run → service → Logs.

`requirements.txt` pins the versions tested locally; after upgrading packages in the `.venv`, test, then update
the pinned versions before redeploying.

If a *Contribute* page is added later (as in the NSBI Smart Building Mapping app), contributions must be written to a
private Cloud Storage bucket mounted in the container (Cloud Run's own disk is temporary); see that app's
`docs/deployment.md`.
