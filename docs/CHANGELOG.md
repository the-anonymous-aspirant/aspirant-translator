# Changelog

## 1.0.0

Extracted from aspirant-online monorepo into standalone service.

- Translator service now lives in its own repository (`aspirant-translator`)
- Dockerfile updated: paths no longer have `translator/` prefix since code is at the repo root
- Added CI workflow (test + build-and-push to GHCR)
- Added standalone documentation (README, CLAUDE.md, docs/)
- No functional changes to the translation logic
