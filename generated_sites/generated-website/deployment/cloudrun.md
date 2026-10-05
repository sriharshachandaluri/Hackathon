# Cloud Run deployment

Build and deploy this container after reviewing generated code. Set secrets with Secret Manager or environment configuration; never commit credentials. Example:

```sh
gcloud run deploy SITE_NAME --source . --region REGION --allow-unauthenticated
```

This generator prepares files only. Run the command in an authenticated Google Cloud project to deploy and obtain a live URL.
