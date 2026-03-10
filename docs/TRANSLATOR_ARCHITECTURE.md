# Translator Architecture

## System Overview

```
                    HTTP Clients
                         |
                         v
              +---------------------+
              |      FastAPI App    |
              |   (app/main.py)     |
              |                     |
              |  lifespan manager   |
              |  - init on startup  |
              |  - refresh index    |
              +----------+----------+
                         |
                         v
              +---------------------+
              |    Router Layer     |
              |   (app/routes.py)   |
              |                     |
              |  GET  /health       |
              |  GET  /languages    |
              |  POST /languages/   |
              |       install       |
              |  POST /translations |
              +----------+----------+
                         |
                         v
              +---------------------+
              |   Model Manager    |
              | (app/model_manager) |
              |                     |
              | +------+  +------+ |
              | | LRU  |  |Thread| |
              | |Cache |  | Lock | |
              | |(<=6) |  |      | |
              | +------+  +------+ |
              |                     |
              | - ensure_installed  |
              | - _load_model       |
              | - translate_text    |
              | - get_avail_pairs   |
              +---+------------+----+
                  |            |
                  v            v
        +--------------+  +------------------+
        |    Argos     |  |  /data/models    |
        |  Translate   |  | (Docker volume)  |
        |   Library    |  |                  |
        |              |  | - .argosmodel    |
        | - package    |  |   files          |
        | - translate  |  | - package index  |
        | - settings   |  |                  |
        +--------------+  +------------------+
```

## Component Breakdown

### FastAPI App (`app/main.py`)

Entry point. Configures logging, sets up the lifespan context manager (which calls `model_manager.initialize()` on startup), and mounts the router.

### Router (`app/routes.py`)

Four endpoints with Pydantic request/response validation. Each endpoint delegates to `model_manager` for business logic. Error handling maps domain exceptions (`UnsupportedPairError`, `DownloadError`, `ModelLoadError`) to HTTP status codes.

### Model Manager (`app/model_manager.py`)

Core logic module with three responsibilities:

1. **Package management** -- `ensure_installed()` checks disk, downloads if missing
2. **Memory management** -- `_load_model()` implements LRU cache with thread-safe eviction
3. **Translation routing** -- `translate_text()` handles direct pairs and pivot-through-English

All `argostranslate` imports are lazy (inside functions) to allow test mocking without the real library installed.

### Configuration (`app/config.py`)

Environment-driven settings with sensible defaults. Three knobs: `MAX_LOADED_MODELS`, `MAX_TEXT_LENGTH`, `ARGOS_PACKAGES_PATH`.

## Data Flow

### Translation Request

```
Client                  routes.py              model_manager.py           Argos
  |                        |                        |                       |
  |-- POST /translations ->|                        |                       |
  |                        |-- translate_text() --->|                       |
  |                        |                        |-- check direct pair   |
  |                        |                        |   available?          |
  |                        |                        |                       |
  |                        |                        |-- ensure_installed -->|
  |                        |                        |   (download if new)   |
  |                        |                        |<- installed ----------|
  |                        |                        |                       |
  |                        |                        |-- _load_model ------>|
  |                        |                        |   (LRU eviction)      |
  |                        |                        |<- translation obj ---|
  |                        |                        |                       |
  |                        |                        |-- obj.translate() -->|
  |                        |                        |<- translated text ---|
  |                        |<- result --------------|                       |
  |<- JSON response -------|                        |                       |
```

### LRU Cache Behavior

```
Capacity: 6 slots

Request en->sv:  [en->sv]                          (1/6, loaded)
Request en->de:  [en->sv, en->de]                  (2/6, loaded)
Request en->fr:  [en->sv, en->de, en->fr]          (3/6, loaded)
Request en->sv:  [en->de, en->fr, en->sv]          (3/6, moved to end)
  ...fill to 6...
Request en->ja:  [en->fr, en->sv, ..., en->ja]     (6/6, en->de evicted)
```

## Docker Setup

```
+----------------------------------+
|  Docker Container                |
|                                  |
|  /app/                           |
|    app/                          |
|      __init__.py                 |
|      config.py                   |
|      main.py                     |
|      model_manager.py            |
|      routes.py                   |
|                                  |
|  Port 8000 (uvicorn)             |
|                                  |
+--------+-------------------------+
         |
         v (mount)
+------------------+
| translatordata   |
| Docker volume    |
|                  |
| /data/models/    |
|   packages/      |
|   index.json     |
+------------------+
```

The volume persists model packages across container restarts. The container itself is stateless and can be replaced at any time without data loss.
