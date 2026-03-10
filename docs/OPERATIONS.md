# Translator Operations

Setup, running, testing, and debugging instructions for the translator service.

## Setup

### Prerequisites

- Docker (for running the service)
- Python 3.11+ (for running tests locally)

### Build the Docker Image

```bash
docker build -t aspirant-translator .
```

The build installs CPU-only PyTorch and all Python dependencies. No model packages are included in the image -- they are downloaded on demand at runtime.

## Running

### With Docker

```bash
# Create a named volume for persistent model storage
docker volume create translatordata

# Run the service
docker run -p 8000:8000 -v translatordata:/data/models aspirant-translator
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_LOADED_MODELS` | 6 | Max models in memory |
| `MAX_TEXT_LENGTH` | 5000 | Max characters per request |
| `ARGOS_PACKAGES_PATH` | `/data/models` | Model storage path |

Override at runtime:

```bash
docker run -p 8000:8000 \
  -e MAX_LOADED_MODELS=4 \
  -v translatordata:/data/models \
  aspirant-translator
```

### Verify the Service

```bash
# Health check
curl http://localhost:8000/health

# List available languages
curl http://localhost:8000/languages

# Translate text
curl -X POST http://localhost:8000/translations \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello", "source_language": "en", "target_language": "sv"}'
```

## Testing

### Install Test Dependencies

```bash
pip install -r requirements-test.txt
```

Note: `requirements-test.txt` does **not** include `argostranslate`. Tests mock it entirely, so no model downloads or GPU are needed.

### Run Tests

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_translations.py -v

# Specific test
pytest tests/test_model_manager.py::TestLRUEviction -v
```

### Test Structure

| File | Coverage |
|------|----------|
| `tests/conftest.py` | Shared fixtures, argos mocking |
| `tests/test_health.py` | Health endpoint |
| `tests/test_languages.py` | Language listing and installation |
| `tests/test_translations.py` | Translation endpoint validation and error cases |
| `tests/test_model_manager.py` | LRU eviction, pivot translation, package installation |

## Debugging

### Common Issues

**Service starts but /health shows "degraded":**
- `argos_translate: unavailable` -- The argostranslate package failed to import. Check container logs for import errors.
- `models_volume: not_writable` -- The `/data/models` directory is not writable. Ensure the Docker volume is mounted correctly.

**First translation request is slow (~30 seconds):**
- This is expected. The service downloads the model package on first use. Subsequent requests for the same pair will be fast.

**Translation returns 503 `download_failed`:**
- The container cannot reach the Argos package index. Check network connectivity from inside the container.

**Translation returns 503 `model_load_failed`:**
- The model package is installed but cannot be loaded. This may indicate a corrupted package. Delete the volume and let the service re-download.

### Viewing Logs

```bash
# Follow container logs
docker logs -f <container_id>
```

Log output includes:
- Startup initialization messages
- Package download/install events
- Model load/evict events with cache occupancy (e.g., "Loaded model en -> sv into memory (3/6)")
- Pivot translation routing

### Inspecting the Model Volume

```bash
# List installed packages
docker exec <container_id> ls -la /data/models/

# Check volume size
docker system df -v | grep translatordata
```

### Clearing the Model Cache

To force re-download of all models:

```bash
docker volume rm translatordata
docker volume create translatordata
```
