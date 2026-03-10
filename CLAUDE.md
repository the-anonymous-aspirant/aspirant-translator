# CLAUDE.md

## Service Description

aspirant-translator is a stateless REST microservice for text translation using [Argos Translate](https://github.com/argosopentech/argos-translate), a fully offline, open-source machine translation library. It supports 52 languages and 139 translation pairs with on-demand model downloading and LRU memory management.

This service follows [aspirant-meta conventions](https://github.com/the-anonymous-aspirant/aspirant-meta/blob/main/CONVENTIONS.md) for API contract, logging, testing, and Docker standards.

## How to Run

```bash
# Build the Docker image
docker build -t aspirant-translator .

# Run the container (with persistent model volume)
docker run -p 8000:8000 -v translatordata:/data/models aspirant-translator
```

## How to Test

```bash
# Install test dependencies (no argostranslate needed — tests mock it)
pip install -r requirements-test.txt

# Run tests
pytest tests/ -v
```

## Port

The service listens on port **8000** inside the container.

## API Endpoints

| Method | Path                 | Description                          |
|--------|----------------------|--------------------------------------|
| GET    | `/health`            | Health check with dependency status  |
| GET    | `/languages`         | List available language pairs        |
| POST   | `/languages/install` | Download and install a language pair |
| POST   | `/translations`      | Translate text between languages     |

## Key Architecture Details

- **LRU cache**: Max 6 loaded models in memory (configurable via `MAX_LOADED_MODELS`)
- **Pivot translation**: Language pairs without a direct model pivot through English automatically
- **On-demand download**: Models are downloaded from the Argos index on first use and persisted to a Docker volume
- **Lazy imports**: `argostranslate` is imported lazily inside functions to keep tests fast and independent

## Configuration

| Environment Variable  | Default       | Description                                  |
|-----------------------|---------------|----------------------------------------------|
| `MAX_LOADED_MODELS`   | 6             | Max language pair models in memory            |
| `MAX_TEXT_LENGTH`     | 5000          | Maximum characters per translation request    |
| `ARGOS_PACKAGES_PATH` | `/data/models`| Volume mount path for downloaded model packages |
