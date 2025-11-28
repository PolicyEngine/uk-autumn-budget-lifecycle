# Lifetime policy impact calculator

Interactive tool modelling the impact of UK budget policy reforms on a graduate over their working life.

## Local development

```bash
# Start the API (requires Python 3.12+)
cd backend && uvicorn main:app --reload --port 8000

# Open frontend/index.html in a browser
```

Or use the Makefile:
```bash
make dev
```

## Deployment

### Backend (Google Cloud Run)

1. Build and push the Docker image:
```bash
cd backend
gcloud builds submit --tag gcr.io/YOUR_PROJECT/lifetime-impact-api
```

2. Deploy to Cloud Run:
```bash
gcloud run deploy lifetime-impact-api \
  --image gcr.io/YOUR_PROJECT/lifetime-impact-api \
  --platform managed \
  --region europe-west1 \
  --allow-unauthenticated
```

3. Note the service URL (e.g. `https://lifetime-impact-api-xxx.run.app`)

### Frontend (Vercel)

1. Update the API URL in `frontend/index.html`:
```javascript
window.API_URL = 'https://your-cloud-run-url.run.app';
```

2. Deploy to Vercel:
```bash
cd frontend
vercel --prod
```

Or connect the repo to Vercel and set the root directory to `frontend`.

### Environment variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Backend port (Cloud Run sets this automatically) | `8000` |
| `API_URL` | Backend URL for frontend | `http://localhost:8000` |

## Architecture

- **Backend**: FastAPI (Python) - runs the tax/benefit model calculations
- **Frontend**: Static HTML/JS with D3.js - no build step required
