import os

MAX_LOADED_MODELS = int(os.environ.get("MAX_LOADED_MODELS", 6))
MAX_TEXT_LENGTH = int(os.environ.get("MAX_TEXT_LENGTH", 5000))
ARGOS_PACKAGES_PATH = os.environ.get("ARGOS_PACKAGES_PATH", "/data/models")

TRANSLATOR_VERSION = "1.0.0"
SERVICE_NAME = "translator"
