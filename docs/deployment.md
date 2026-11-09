# Deployment (Docker, Google Cloud Run)

The app runs in a Docker container (`Dockerfile`, served by gunicorn: `app:server`). The dataset
(`data/smart_building_education_dataset.xlsx`) is part of the image: after changing it, commit and redeploy.
The app stores nothing on the server (selections are kept in the visitor's browser tab only).

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

## 3. Deploy (and redeploy after each change)

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
