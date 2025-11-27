# Lato Chatbot — FastAPI + Redis + React (local dev)

## Prereqs
- Python 3.10+
- Node 18+ (for frontend)
- Docker (optional, recommended for Redis)

## Backend (local, no docker)
1. Copy `lato_products.json` into the project root.
2. Create virtualenv and install requirements:

    python -m venv .venv
    source .venv/bin/activate   # or .venv\Scripts\activate on Windows
    pip install -r requirements.txt

3. Run Redis locally (optional) or set REDIS_URL env var if accessible.
4. Start the API:

    uvicorn fastapi_chatbot:app --reload --port 8000

The API will be at http://localhost:8000

Endpoints:
- POST /chat  { session_id?, message }
- GET /products
- GET /product/{sku_or_name}

## Frontend (React)
1. `cd web-client` (files provided below)
2. `npm install`
3. `npm start` (runs on port 3000 by default)

The React client calls the backend at http://localhost:8000 — update the base URL in `src/api.js` if needed.

## SharePoint images
- If images live on SharePoint, you can directly store the public/guest link in `image_url` fields in the JSON.
- If SharePoint requires auth, set up a small proxy on the backend that fetches images server-side using an app token and returns them (recommended for secure access).

## Production suggestions
- Move sessions to Redis (already supported when REDIS_URL is set).
- Protect product endpoints with an API key or authentication if needed.
- Serve React app from a static host and use HTTPS. For images, use a CDN to improve performance.
```
> Note: `aioredis` is optional if you won't use Redis. You can remove it if you prefer in-memory.
---