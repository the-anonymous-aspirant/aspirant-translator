import logging
import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.config import MAX_TEXT_LENGTH, SERVICE_NAME, TRANSLATOR_VERSION
from app import model_manager
from app.model_manager import DownloadError, ModelLoadError, UnsupportedPairError

logger = logging.getLogger(__name__)
router = APIRouter()


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


# --- Schemas ---

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    checks: dict


class LanguageInstallRequest(BaseModel):
    source_language: str
    target_language: str


class TranslateRequest(BaseModel):
    text: str
    source_language: str
    target_language: str


# --- Endpoints ---

@router.get("/health")
def health_check():
    checks = {}

    # Check argos importable
    try:
        import argostranslate.translate  # noqa: F401
        checks["argos_translate"] = "available"
    except Exception:
        checks["argos_translate"] = "unavailable"

    # Check volume writable
    try:
        from app.config import ARGOS_PACKAGES_PATH
        import os
        test_file = os.path.join(ARGOS_PACKAGES_PATH, ".write_test")
        os.makedirs(ARGOS_PACKAGES_PATH, exist_ok=True)
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        checks["models_volume"] = "writable"
    except Exception:
        checks["models_volume"] = "not_writable"

    all_ok = all(
        v in ("available", "writable") for v in checks.values()
    )

    return HealthResponse(
        status="ok" if all_ok else "degraded",
        service=SERVICE_NAME,
        version=TRANSLATOR_VERSION,
        checks=checks,
    )


@router.get("/languages")
def list_languages():
    return model_manager.get_available_pairs()


@router.post("/languages/install")
def install_language(body: LanguageInstallRequest):
    try:
        newly_installed = model_manager.ensure_installed(
            body.source_language, body.target_language
        )
    except UnsupportedPairError as exc:
        return _error(400, "unsupported_language_pair", str(exc))
    except DownloadError as exc:
        return _error(503, "download_failed", str(exc))

    if newly_installed:
        return JSONResponse(
            status_code=201,
            content={
                "source_language": body.source_language,
                "target_language": body.target_language,
                "status": "installed",
                "message": "Package downloaded and installed.",
            },
        )

    return {
        "source_language": body.source_language,
        "target_language": body.target_language,
        "status": "installed",
        "message": "Package already installed.",
    }


@router.post("/translations")
def translate(body: TranslateRequest):
    # Validation
    if not body.text or not body.text.strip():
        return _error(400, "validation_error", "Text is required.")

    if len(body.text) > MAX_TEXT_LENGTH:
        return _error(
            400, "validation_error",
            f"Text exceeds maximum length of {MAX_TEXT_LENGTH} characters.",
        )

    if body.source_language == body.target_language:
        return _error(
            400, "validation_error",
            "Source and target language must be different.",
        )

    start = time.time()
    try:
        translated = model_manager.translate_text(
            body.text, body.source_language, body.target_language
        )
    except UnsupportedPairError as exc:
        return _error(400, "unsupported_language_pair", str(exc))
    except DownloadError as exc:
        return _error(503, "download_failed", str(exc))
    except ModelLoadError as exc:
        return _error(503, "model_load_failed", str(exc))

    elapsed = round(time.time() - start, 3)

    return {
        "text": body.text,
        "translated_text": translated,
        "source_language": body.source_language,
        "target_language": body.target_language,
        "characters": len(body.text),
        "processing_time_seconds": elapsed,
    }
