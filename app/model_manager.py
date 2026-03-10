import logging
import threading
from collections import OrderedDict

from app.config import MAX_LOADED_MODELS

logger = logging.getLogger(__name__)

# LRU cache of loaded translation objects keyed by (source, target)
_loaded_models: OrderedDict = OrderedDict()
_lock = threading.Lock()


class UnsupportedPairError(Exception):
    pass


class DownloadError(Exception):
    pass


class ModelLoadError(Exception):
    pass


def initialize():
    """Redirect Argos storage to volume path and refresh package index."""
    from pathlib import Path
    import argostranslate.package
    import argostranslate.settings
    from app.config import ARGOS_PACKAGES_PATH

    argostranslate.settings.data_dir = Path(ARGOS_PACKAGES_PATH)

    logger.info("Refreshing Argos package index...")
    try:
        argostranslate.package.update_package_index()
    except Exception as exc:
        logger.warning("Failed to refresh package index: %s", exc)

    installed = argostranslate.package.get_installed_packages()
    logger.info("Argos initialized. %d package(s) installed on volume.", len(installed))


def get_available_pairs():
    """Return language list with installed status per target."""
    import argostranslate.package

    available = argostranslate.package.get_available_packages()
    installed = argostranslate.package.get_installed_packages()

    installed_set = set()
    for pkg in installed:
        installed_set.add((pkg.from_code, pkg.to_code))

    # Build language map: code -> {name, targets}
    lang_map = {}
    for pkg in available:
        src_code = pkg.from_code
        src_name = pkg.from_name
        tgt_code = pkg.to_code

        if src_code not in lang_map:
            lang_map[src_code] = {"code": src_code, "name": src_name, "targets": []}

        lang_map[src_code]["targets"].append({
            "code": tgt_code,
            "installed": (src_code, tgt_code) in installed_set,
        })

    languages = sorted(lang_map.values(), key=lambda x: x["code"])
    total_pairs = sum(len(lang["targets"]) for lang in languages)
    installed_pairs = len(installed_set)

    return {
        "languages": languages,
        "total_pairs": total_pairs,
        "installed_pairs": installed_pairs,
    }


def ensure_installed(src, tgt):
    """Check if pair is installed, download if missing. Returns True if newly installed."""
    import argostranslate.package

    installed = argostranslate.package.get_installed_packages()
    for pkg in installed:
        if pkg.from_code == src and pkg.to_code == tgt:
            return False  # Already installed

    # Find in available packages
    available = argostranslate.package.get_available_packages()
    target_pkg = None
    for pkg in available:
        if pkg.from_code == src and pkg.to_code == tgt:
            target_pkg = pkg
            break

    if target_pkg is None:
        raise UnsupportedPairError(
            f"No package available for {src} -> {tgt}"
        )

    logger.info("Downloading package %s -> %s...", src, tgt)
    try:
        argostranslate.package.install_from_path(target_pkg.download())
    except Exception as exc:
        raise DownloadError(f"Failed to download {src} -> {tgt}: {exc}") from exc

    logger.info("Package %s -> %s installed.", src, tgt)
    return True  # Newly installed


def _load_model(src, tgt):
    """Load a translation model into memory with LRU eviction."""
    import argostranslate.translate

    with _lock:
        # Check if already loaded
        if (src, tgt) in _loaded_models:
            _loaded_models.move_to_end((src, tgt))
            return _loaded_models[(src, tgt)]

        # Find the installed language pair
        installed_languages = argostranslate.translate.get_installed_languages()
        src_lang = None
        tgt_lang = None
        for lang in installed_languages:
            if lang.code == src:
                src_lang = lang
            if lang.code == tgt:
                tgt_lang = lang

        if src_lang is None or tgt_lang is None:
            raise ModelLoadError(
                f"Languages not found for {src} -> {tgt}"
            )

        translation = src_lang.get_translation(tgt_lang)
        if translation is None:
            raise ModelLoadError(
                f"Translation object not found for {src} -> {tgt}"
            )

        # Evict LRU if at capacity
        while len(_loaded_models) >= MAX_LOADED_MODELS:
            evicted_key, _ = _loaded_models.popitem(last=False)
            logger.info("Evicted model %s -> %s from memory.", *evicted_key)

        _loaded_models[(src, tgt)] = translation
        logger.info(
            "Loaded model %s -> %s into memory (%d/%d).",
            src, tgt, len(_loaded_models), MAX_LOADED_MODELS,
        )
        return translation


def translate_text(text, src, tgt):
    """Translate text, using pivot through English if no direct pair exists."""
    import argostranslate.package

    # Check if direct pair is available
    available = argostranslate.package.get_available_packages()
    has_direct = any(
        pkg.from_code == src and pkg.to_code == tgt for pkg in available
    )

    if has_direct:
        ensure_installed(src, tgt)
        translation = _load_model(src, tgt)
        return translation.translate(text)

    # Pivot through English
    if src == "en" or tgt == "en":
        raise UnsupportedPairError(
            f"No package available for {src} -> {tgt}"
        )

    logger.info("Pivoting %s -> en -> %s", src, tgt)
    ensure_installed(src, "en")
    ensure_installed("en", tgt)

    translation_to_en = _load_model(src, "en")
    intermediate = translation_to_en.translate(text)

    translation_from_en = _load_model("en", tgt)
    return translation_from_en.translate(intermediate)
