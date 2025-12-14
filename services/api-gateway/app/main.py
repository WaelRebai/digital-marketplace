from fastapi import FastAPI
import httpx

app = FastAPI(title="API Gateway")

@app.get("/health")
async def health():
    return {"status": "ok"}
