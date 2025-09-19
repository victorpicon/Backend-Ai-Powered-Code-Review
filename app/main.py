from app.api.reviews import viewer as reviews
from fastapi import FastAPI

app = FastAPI(title="AI Code Review API")

# incluir rotas
app.include_router(reviews.router, prefix="/api/reviews", tags=["reviews"])


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}
