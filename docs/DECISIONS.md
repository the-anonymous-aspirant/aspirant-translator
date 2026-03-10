# Design Decisions

Key architectural and implementation decisions for the translator service.

## CPU-Only PyTorch

**Decision:** Install PyTorch with CPU-only wheels (`--index-url https://download.pytorch.org/whl/cpu`).

**Rationale:** Argos Translate depends on PyTorch for its neural translation models. The full PyTorch package with CUDA support is ~2 GB and requires GPU drivers. Since the translator handles short text (max 5000 chars) and translation latency of 50-200ms is acceptable, CPU inference is sufficient. This keeps the Docker image small (~500 MB vs ~2.5 GB) and avoids GPU infrastructure complexity.

## Lazy Imports for Testability

**Decision:** All `argostranslate` imports happen inside function bodies, not at module level.

**Rationale:** The `argostranslate` package has heavy dependencies (PyTorch, sentencepiece, stanza) that are slow to install and not needed for testing. By importing lazily, the test suite can inject mock modules via `sys.modules.setdefault()` in `conftest.py` before any real imports occur. This means tests run in seconds without downloading ~1 GB of dependencies.

## LRU Eviction (Max 6 Models)

**Decision:** Keep at most 6 translation models loaded in memory simultaneously, evicting the least-recently-used when the limit is reached.

**Rationale:** Each loaded model consumes ~150-300 MB of RAM. With a 2 GB container memory limit, 6 models is a safe ceiling that leaves room for the Python runtime and FastAPI overhead. The LRU strategy ensures frequently-used pairs stay warm while rarely-used pairs are evicted. Evicted models remain on disk and can be reloaded in ~2-3 seconds, which is an acceptable cold-start penalty.

The limit is configurable via `MAX_LOADED_MODELS` for environments with more or less memory.

## Pivot Translation Through English

**Decision:** When no direct model exists for a language pair (e.g., Swedish to German), automatically translate through English as a pivot language (Swedish -> English -> German).

**Rationale:** Argos Translate provides ~139 direct language pairs, but not all combinations. English is the most connected language in the Argos package index, with direct pairs to nearly every supported language. Pivoting through English covers most missing pairs with acceptable quality loss. The pivot is transparent to the client -- they request `sv -> de` and receive the final German text without knowing about the intermediate English step.

## On-Demand Model Downloading

**Decision:** Ship the Docker image without any pre-installed model packages. Download models on first use and persist them to a Docker volume.

**Rationale:** Including all 139 model packages would make the image ~30 GB. Most deployments only need a handful of language pairs. On-demand downloading means the image stays small (~500 MB), startup is fast (no model loading), and disk usage grows organically based on actual usage patterns. The Docker volume ensures packages survive container restarts.

The tradeoff is a slower first request for each new language pair (~10-30 seconds for download). This is acceptable for a self-hosted tool where language needs are predictable and the first-request penalty happens only once per pair.

## Stateless Container Design

**Decision:** The container is fully stateless -- all persistent data lives on the Docker volume at `/data/models`.

**Rationale:** This simplifies deployment, scaling, and recovery. The container can be rebuilt, replaced, or rolled back without data loss. The volume is the only piece that needs backup. If the volume is lost, the service gracefully re-downloads models on demand.
