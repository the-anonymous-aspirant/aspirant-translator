# Changelog

## Unreleased

- Builds of main's image now run one at a time, and `:latest` and `:main` go
  only on a build of main's current head (`scripts/is-main-head.sh`, unit test
  `sh tests/is_main_head_unit.sh`). Two merges landing seconds apart, or a
  re-run of an older build, can no longer leave `:latest` on an older commit
  for auto-pull to deploy. Test runs are not queued. See system_3 #9984, from
  #9966 (the same guard as aspirant-client #409).

## 1.0.0

Extracted from aspirant-online monorepo into standalone service.

- Translator service now lives in its own repository (`aspirant-translator`)
- Dockerfile updated: paths no longer have `translator/` prefix since code is at the repo root
- Added CI workflow (test + build-and-push to GHCR)
- Added standalone documentation (README, CLAUDE.md, docs/)
- No functional changes to the translation logic
