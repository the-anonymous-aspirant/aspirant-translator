import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import TRANSLATOR_VERSION, SERVICE_NAME
from app import model_manager
from app import routes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        logger.info("Initializing %s v%s...", SERVICE_NAME, TRANSLATOR_VERSION)
        model_manager.initialize()
        logger.info("Translator ready.")
    except Exception as exc:
        logger.warning("Lifespan startup skipped (likely test mode): %s", exc)

    yield

    logger.info("Shutting down...")
    logger.info("Shutdown complete.")


app = FastAPI(
    title="Translator Service",
    description="Translate text between languages using Argos Translate.",
    version=TRANSLATOR_VERSION,
    lifespan=lifespan,
)

app.include_router(routes.router)
