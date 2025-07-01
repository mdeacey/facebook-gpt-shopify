from fastapi import FastAPI
from facebook_oauth.routes import router as facebook_oauth_router
from shopify_integration.routes import router as shopify_oauth_router
from starlette.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from shopify_integration.utils import daily_poll
import atexit

load_dotenv()

app = FastAPI(title="Facebook and Shopify OAuth with FastAPI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(facebook_oauth_router, prefix="/facebook")
app.include_router(shopify_oauth_router, prefix="/shopify")

@app.get("/")
async def root():
    return {"status": "ok"}

scheduler = BackgroundScheduler()
scheduler.add_job(daily_poll, CronTrigger(hour=0, minute=0))
scheduler.start()

atexit.register(lambda: scheduler.shutdown())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=True)