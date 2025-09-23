# AI Code Review Backend (FastAPI + MongoDB)

Backend API for submitting code snippets and receiving AI-powered reviews. Built with FastAPI, MongoDB, and integrates with Gemini and/or OpenAI.

## Features
- Submit code for asynchronous AI review
- Store reviews in MongoDB with timestamps and status
- Rate limiting: 10 reviews per IP per hour
- List reviews with pagination and filters (language, status, date range)
- Statistics endpoint: overall metrics, common issues, by-language breakdown
- Configurable CORS

## Requirements
- Python 3.10
- Docker and Docker Compose (optional)

## Environment
Create a `.env` file in the project root:

```
GEMINI_API_KEY=your_gemini_key
OPENAI_API_KEY=your_openai_key
MONGODB_URI=mongodb://mongodb:27017
CORS_ALLOW_ORIGINS=*
FRONTEND_URL=http://localhost:3000
BACKEND_URL=http://localhost:8000
```

For local runs without Docker:
```
MONGODB_URI=mongodb://localhost:27017
```

## Run with Docker

```bash
docker-compose up -d --build
```

## Local Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## API Endpoints
- GET `/api/health`
- POST `/api/reviews`
- GET `/api/reviews/{id}`
- GET `/api/reviews?skip=0&limit=10&language=py&status=completed`
- GET `/api/reviews/stats`
- GET `/api/reviews/export` (CSV)
- GET `/api/stats`

## Real-time Updates
- WebSocket: `/api/reviews/ws/{review_id}` streams status until `completed` or `failed`.

## Caching
- Identical submissions (same language+code) return cached feedback instantly via a `code_hash` check.

## Notes
- CORS is configurable via `CORS_ALLOW_ORIGINS` (comma-separated for multiple domains).
- AI provider: the app uses Gemini if `GEMINI_API_KEY` is set; otherwise it tries OpenAI if `OPENAI_API_KEY` is set.
