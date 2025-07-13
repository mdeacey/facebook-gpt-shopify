import uuid
from fastapi import FastAPI, Request
from starlette.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from contextlib import asynccontextmanager

from shared.logging import logger
from integrations.facebook.routes import router as facebook_oauth_router
from integrations.shopify.routes import router as shopify_oauth_router
from integrations.facebook.utils import daily_poll as facebook_daily_poll
from integrations.shopify.utils import daily_poll as shopify_daily_poll


scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not scheduler.running:
        scheduler.add_job(
            shopify_daily_poll,
            CronTrigger(hour=0, minute=0),
            id="shopify_daily_poll",
            replace_existing=True,
        )
        scheduler.add_job(
            facebook_daily_poll,
            CronTrigger(hour=0, minute=0),
            id="facebook_daily_poll",
            replace_existing=True,
        )
        scheduler.start()
        logger.info("Scheduler started with jobs: shopify_daily_poll, facebook_daily_poll")
    yield
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler shut down")


app = FastAPI(title="Facebook and Shopify OAuth with FastAPI", lifespan=lifespan)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    logger.debug(f"[{request_id}] Processing request: {request.url} with headers: {dict(request.headers)}")
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000, reload=False)
