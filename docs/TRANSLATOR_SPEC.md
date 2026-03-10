# Translator Service Specification

A REST microservice that translates text between languages using Argos Translate (local inference). Supports 52 languages and 139 translation pairs with on-demand model downloading and lazy memory loading.

This service follows the [aspirant-meta conventions](https://github.com/the-anonymous-aspirant/aspirant-meta/blob/main/CONVENTIONS.md) for API contract (URL patterns, error responses, pagination, health endpoint), logging, testing, and Docker standards. This spec documents only what is specific to the translator.

## Architecture

The translator runs as a standalone, **stateless** FastAPI container. It has no database dependency -- model packages are stored on a Docker volume and everything else is in-memory.

```
+-----------+  +-----------+  +-------------+  +------------+  +-------------+
|  Client   |  |  Server   |  | Transcriber |  |  Commander |  | Translator  |
|  (Nginx)  |  | (Go/Gin)  |  |  (FastAPI)  |  |  (FastAPI) |  |  (FastAPI)  |
|  :80      |  |  :8081    |  |  :8082      |  |  :8083     |  |  :8084      |
+-----------+  +-----+-----+  +------+------+  +------+-----+  +-------------+
                     |               |               |               |
                     v               v               v               |
              +-----------------------------------+                  |
              |           PostgreSQL              |     +------------v--+
              |             :5432                 |     |translatordata |
              +-----------------------------------+     |  (volume)     |
                                                        +---------------+
```

## API Endpoints

### Health Check

```
GET /health
```

Returns service status following the [standard health endpoint contract](https://github.com/the-anonymous-aspirant/aspirant-meta/blob/main/CONVENTIONS.md#health-endpoint).

**Response:**
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

### List Available Languages

```
GET /languages
```

Returns all known language pairs from the Argos package index. Each language indicates whether its models are already downloaded to the volume or still need to be fetched.

**Response (200):**
```json
{
  "languages": [
    {
      "code": "en",
      "name": "English",
      "targets": [
        {"code": "sv", "installed": true},
        {"code": "de", "installed": true},
        {"code": "es", "installed": false}
      ]
    },
    {
      "code": "sv",
      "name": "Swedish",
      "targets": [
        {"code": "en", "installed": true}
      ]
    }
  ],
  "total_pairs": 139,
  "installed_pairs": 4
}
```

### Install Language Pair

```
POST /languages/install
Content-Type: application/json
```

**Request body:**
```json
{
  "source_language": "en",
  "target_language": "es"
}
```

Downloads and installs a language pair package to the persistent volume. Idempotent -- returns 200 if already installed.

**Response (200):**
```json
{
  "source_language": "en",
  "target_language": "es",
  "status": "installed",
  "message": "Package already installed."
}
```

**Response (201):**
```json
{
  "source_language": "en",
  "target_language": "es",
  "status": "installed",
  "message": "Package downloaded and installed."
}
```

**Error cases:**
- 400 `unsupported_language_pair` -- no package exists for this pair
- 503 `download_failed` -- network error during package download

### Translate Text

```
POST /translations
Content-Type: application/json
```

**Request body:**
```json
{
  "text": "Hello, how are you?",
  "source_language": "en",
  "target_language": "sv"
}
```

- `text` (required) -- Text to translate (max 5000 characters)
- `source_language` (required) -- ISO 639-1 language code
- `target_language` (required) -- ISO 639-1 language code

Translation is synchronous -- the model is small enough to return results inline.

If the language pair is not yet downloaded, the service automatically downloads and installs it on the first request. This means:
- **First-ever request for a new pair:** ~10-30 seconds (download + install + load)
- **Subsequent cold requests** (downloaded but not in memory): ~2-3 seconds (load from disk)
- **Warm requests** (model already in memory): ~50-200ms

**Response (200):**
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

**Error cases:**
- 400 `validation_error` -- text too long, missing fields, same source/target
- 400 `unsupported_language_pair` -- no package exists for the requested pair in the Argos index
- 503 `download_failed` -- language pair package could not be downloaded (network error)
- 503 `model_load_failed` -- language pair model could not be loaded into memory

## Model Management

### Two-Level Lazy Loading

Model management has two distinct layers: **disk** (downloaded packages) and **memory** (loaded models).

```
+-----------------------------------------------------------+
|                    Argos Package Index                     |
|               (remote, 139 pairs available)               |
+-----------------------------+-----------------------------+
                              |  download on first request
                              v
+-----------------------------------------------------------+
|              translatordata volume (disk)                  |
|          (persists across container restarts)              |
|     packages grow organically based on actual usage        |
+-----------------------------+-----------------------------+
                              |  load into memory on use
                              v
+-----------------------------------------------------------+
|              In-memory LRU cache                          |
|        (max MAX_LOADED_MODELS pairs, default 6)           |
|       evicts least-recently-used when full                 |
+-----------------------------------------------------------+
```

#### Layer 1: On-demand download to volume

- The Docker image ships with only the Argos Translate library -- **no model packages**
- On the first translation request (or explicit `POST /languages/install`), the service checks if the required package exists in the `translatordata` volume
- If not present, it downloads the package from the Argos package index and installs it to the volume
- The volume persists across container restarts -- packages are only downloaded once
- Smart check: `argostranslate.package.get_installed_packages()` is compared against the requested pair before attempting any download

#### Layer 2: LRU memory loading

- Downloaded packages are loaded into memory on first translation request for that pair
- When loaded models exceed `MAX_LOADED_MODELS` (default 6), the least-recently-used pair is evicted from memory
- Evicted models remain on disk -- reloading from the volume is fast (~2-3 seconds)
- A threading lock protects model load/evict operations

#### Startup behavior

On startup the service:
1. Refreshes the Argos package index (list of available remote packages)
2. Scans the `translatordata` volume for already-installed packages
3. Does **not** load any models into memory (fully lazy)

#### Request flow

```
POST /translations {source: "en", target: "sv"}
  |
  +-- Is en->sv loaded in memory?
  |   YES -> translate immediately
  |   NO  |
  |        v
  +-- Is en->sv installed on disk (volume)?
  |   YES -> load into memory (evict LRU if needed) -> translate
  |   NO  |
  |        v
  +-- Does en->sv exist in the Argos package index?
  |   YES -> download to volume -> install -> load into memory -> translate
  |   NO  -> return 400 unsupported_language_pair
  |
  +-- Network error during download?
      -> return 503 download_failed
```

### Pivot Translation

For language pairs without a direct model (e.g., Swedish -> German), the service automatically chains through English as a pivot:

```
Swedish -> English -> German
```

Both legs (sv->en and en->de) go through the same download/load flow independently. The client sends `sv` -> `de` and receives the final result -- pivoting is transparent.

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| MAX_LOADED_MODELS | 6 | Max language pair models in memory simultaneously |
| MAX_TEXT_LENGTH | 5000 | Maximum characters per translation request |
| ARGOS_PACKAGES_PATH | /data/models | Volume mount path for downloaded model packages |

## Resource Requirements

- **Docker image:** ~500 MB (Python + Argos Translate library, no model packages)
- **RAM:** ~150-300 MB per loaded model pair, 2 GB container limit with 6 pairs max in memory
- **Disk (volume):** grows on demand -- ~200 MB per installed pair, up to ~30 GB if all 139 pairs are downloaded
- **CPU:** Translation is CPU-bound but fast for text (unlike audio transcription)
- **Network:** Required only when downloading a new language pair for the first time
- **Port:** 8000 (container)
