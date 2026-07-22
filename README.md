# DeadVisionAi

Full-stack AI platform combining local inference, vector search, and intelligent routing.

## Stack

- **Frontend**: Vite + React
- **Backend**: Python / FastAPI
- **Inference**: llama.cpp server
- **Memory**: Qdrant + Redis
- **Search**: SearXNG

## Features

- Multi-provider LLM routing (local + cloud)
- Semantic caching and episodic memory
- Free-tier-aware provider selection
- Web UI for chat and model management

## Running

```bash
# backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000

# frontend
cd frontend
npm install
npm run dev
```

## Config

Copy `.env.example` to `.env` and fill provider API keys. The backend loads settings from environment variables via pydantic-settings.
