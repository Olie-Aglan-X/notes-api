from fastapi import FastAPI
from fastapi.responses import Response
from prometheus_client import Counter, generate_latest

app = FastAPI(title="Notes Search API")

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint"]
)

@app.middleware("http")
async def count_requests(request, call_next):
    response = await call_next(request)
    REQUEST_COUNT.labels(request.method, request.url.path).inc()
    return response

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/ingest")
def ingest():
    return {"message": "ingest placeholder"}

@app.get("/search")
def search():
    return {"message": "search placeholder"}

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type="text/plain")
