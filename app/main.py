from app.api.reviews import viewer as reviews
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="AI Code Review API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# incluir rotas
app.include_router(reviews.router, prefix="/api/reviews", tags=["reviews"])


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}
