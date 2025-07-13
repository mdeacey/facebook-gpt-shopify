from fastapi import FastAPI, Request
from shared.logging import setup_logging
from integrations.facebook.routes import router as facebook_oauth_router
from integrations.shopify.routes import router as shopify_oauth_router
from starlette.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from integrations.facebook.utils import daily_poll as facebook_daily_poll
from integrations.shopify.utils import daily_poll as shopify_daily_poll
import atexit
import logging
import uuid

setup_logging(log_level=logging.INFO, log_file="app.log")

app = FastAPI(title="Facebook and Shopify OAuth with FastAPI")

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request.state.request_id = str(uuid.uuid4())
    response = await call_next(request)
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(facebook_oauth_router, prefix="/facebook")
app.include_router(shopify_oauth_router, prefix="/shopify")

@app.get("/")
async def root():
    return {"status": "ok"}

scheduler = BackgroundScheduler()
if not scheduler.running:
    scheduler.add_job(shopify_daily_poll, CronTrigger(hour=0, minute=0), id="shopify_daily_poll")
    scheduler.add_job(facebook_daily_poll, CronTrigger(hour=0, minute=0), id="facebook_daily_poll")
    scheduler.start()

atexit.register(lambda: scheduler.shutdown())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=True)