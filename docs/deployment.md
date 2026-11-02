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

Replace `PROJECT_ID` and `REGION` (e.g. `europe-north1`, Finland).

```bash
gcloud config set project PROJECT_ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
```

## 3. Deploy (and redeploy after each change)

From the project root (Cloud Build builds the image from the `Dockerfile`):

```bash
gcloud run deploy nsbi-smart-building-education --source . --region REGION --allow-unauthenticated --max-instances 3
```

If a *Contribute* page is added later (as in the NSBI Smart Building Mapping app), contributions must be written to a
private Cloud Storage bucket mounted in the container (Cloud Run's own disk is temporary); see that app's
`docs/deployment.md`.
