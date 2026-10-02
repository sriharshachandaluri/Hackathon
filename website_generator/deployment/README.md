# Deployment

The Deployment Agent creates a Dockerfile and Cloud Run instructions after a saved PASS report. It deliberately does not invoke `gcloud` or publish a service. Review generated code, configure Google Cloud authentication, and deploy from the generated project directory. Supply secrets through Secret Manager or environment variables, never source files.
