# aspirant-translator

A stateless REST microservice for text translation using [Argos Translate](https://github.com/argosopentech/argos-translate). Fully offline, open-source machine translation supporting 52 languages and 139 translation pairs.

## Quick Start

```bash
# Build
docker build -t aspirant-translator .

# Run (with persistent model storage)
docker run -p 8000:8000 -v translatordata:/data/models aspirant-translator

# Translate
curl -X POST http://localhost:8000/translations \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world", "source_language": "en", "target_language": "sv"}'
```

## API Reference

### GET /health

Returns service status and dependency checks.

```json
{
  "status": "ok",
  "service": "translator",
  "version": "1.0.0",
  "checks": {
    "argos_translate": "available",
    "models_volume": "writable"
  }
}
```

### GET /languages

Returns all available language pairs with installation status.

```json
{
  "languages": [
    {
      "code": "en",
      "name": "English",
      "targets": [
        {"code": "sv", "installed": true},
        {"code": "de", "installed": false}
      ]
    }
  ],
  "total_pairs": 139,
  "installed_pairs": 2
}
```

### POST /languages/install

Pre-downloads a language pair model to the persistent volume.

**Request:**
```json
{
  "source_language": "en",
  "target_language": "sv"
}
```

**Response (201 newly installed / 200 already installed):**
```json
{
  "source_language": "en",
  "target_language": "sv",
  "status": "installed",
  "message": "Package downloaded and installed."
}
```

### POST /translations

Translates text between languages. Models are downloaded on-demand if not yet installed.

**Request:**
```json
{
  "text": "Hello, how are you?",
  "source_language": "en",
  "target_language": "sv"
}
```

**Response:**
```json
{
  "text": "Hello, how are you?",
  "translated_text": "Hej, hur m\u00e5r du?",
  "source_language": "en",
  "target_language": "sv",
  "characters": 19,
  "processing_time_seconds": 0.12
}
```

## Architecture Overview

```
                         POST /translations
                                |
                                v
                    +-------------------+
                    |   FastAPI (routes) |
                    +-------------------+
                                |
                                v
                    +-------------------+
                    |  Model Manager    |
                    |  - LRU cache (6)  |
                    |  - pivot via EN   |
                    |  - auto-download  |
                    +-------------------+
                           |         |
                           v         v
                  +------------+  +------------------+
                  |   Argos    |  | /data/models     |
                  | Translate  |  | (Docker volume)  |
                  +------------+  +------------------+
```

- **FastAPI app** handles HTTP routing, validation, and error responses
- **Model Manager** orchestrates model downloading, LRU caching, and pivot translation
- **Argos Translate** provides the actual neural machine translation
- **Docker volume** persists downloaded model packages across container restarts

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_LOADED_MODELS` | 6 | Max models held in memory simultaneously |
| `MAX_TEXT_LENGTH` | 5000 | Max characters per translation request |
| `ARGOS_PACKAGES_PATH` | `/data/models` | Path for downloaded model packages |

## Testing

```bash
pip install -r requirements-test.txt
pytest tests/ -v
```

Tests mock `argostranslate` entirely -- no model downloads or GPU required.

## Documentation

See [docs/](docs/) for detailed specifications:

- [SPEC.md](docs/SPEC.md) -- Full API specification
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) -- Architecture details
- [OPERATIONS.md](docs/OPERATIONS.md) -- Setup, run, test, debug
- [DECISIONS.md](docs/DECISIONS.md) -- Key design decisions
- [CHANGELOG.md](docs/CHANGELOG.md) -- Release history
