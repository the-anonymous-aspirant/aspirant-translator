import pytest
from unittest.mock import patch, MagicMock
from collections import OrderedDict


@pytest.fixture(autouse=True)
def reset_model_cache():
    """Reset the model manager's internal state before each test."""
    from app import model_manager
    model_manager._loaded_models.clear()
    yield
    model_manager._loaded_models.clear()


def _make_package(from_code, to_code, from_name=None):
    pkg = MagicMock()
    pkg.from_code = from_code
    pkg.to_code = to_code
    pkg.from_name = from_name or from_code.capitalize()
    return pkg


def _make_language(code, translations=None):
    lang = MagicMock()
    lang.code = code
    lang.get_translation = MagicMock(return_value=translations)
    return lang


class TestEnsureInstalled:
    @patch("argostranslate.package")
    def test_already_installed(self, mock_pkg):
        from app.model_manager import ensure_installed

        installed = _make_package("en", "sv")
        mock_pkg.get_installed_packages.return_value = [installed]

        result = ensure_installed("en", "sv")
        assert result is False
        mock_pkg.install_from_path.assert_not_called()

    @patch("argostranslate.package")
    def test_download_and_install(self, mock_pkg):
        from app.model_manager import ensure_installed

        mock_pkg.get_installed_packages.return_value = []
        available = _make_package("en", "sv")
        available.download.return_value = "/tmp/fake.argosmodel"
        mock_pkg.get_available_packages.return_value = [available]

        result = ensure_installed("en", "sv")
        assert result is True
        available.download.assert_called_once()
        mock_pkg.install_from_path.assert_called_once_with("/tmp/fake.argosmodel")

    @patch("argostranslate.package")
    def test_unsupported_pair(self, mock_pkg):
        from app.model_manager import ensure_installed, UnsupportedPairError

        mock_pkg.get_installed_packages.return_value = []
        mock_pkg.get_available_packages.return_value = []

        with pytest.raises(UnsupportedPairError):
            ensure_installed("en", "zz")


class TestLRUEviction:
    @patch("argostranslate.translate")
    @patch("app.model_manager.MAX_LOADED_MODELS", 2)
    def test_evicts_lru_when_full(self, mock_translate):
        from app import model_manager

        # Pre-populate cache with 2 models
        mock_trans_a = MagicMock()
        mock_trans_b = MagicMock()
        model_manager._loaded_models[("en", "sv")] = mock_trans_a
        model_manager._loaded_models[("en", "de")] = mock_trans_b

        # Set up mock for loading a new model
        en_lang = _make_language("en")
        fr_lang = _make_language("fr")
        mock_trans_c = MagicMock()
        en_lang.get_translation.return_value = mock_trans_c
        mock_translate.get_installed_languages.return_value = [en_lang, fr_lang]

        result = model_manager._load_model("en", "fr")
        assert result == mock_trans_c
        # LRU (en, sv) should have been evicted
        assert ("en", "sv") not in model_manager._loaded_models
        assert ("en", "de") in model_manager._loaded_models
        assert ("en", "fr") in model_manager._loaded_models

    @patch("argostranslate.translate")
    def test_moves_to_end_on_access(self, mock_translate):
        from app import model_manager

        mock_trans_a = MagicMock()
        mock_trans_b = MagicMock()
        model_manager._loaded_models[("en", "sv")] = mock_trans_a
        model_manager._loaded_models[("en", "de")] = mock_trans_b

        # Access (en, sv) — should move to end
        result = model_manager._load_model("en", "sv")
        assert result == mock_trans_a
        keys = list(model_manager._loaded_models.keys())
        assert keys[-1] == ("en", "sv")


class TestPivotTranslation:
    @patch("app.model_manager._load_model")
    @patch("app.model_manager.ensure_installed")
    @patch("argostranslate.package")
    def test_pivot_through_english(self, mock_pkg, mock_ensure, mock_load):
        from app.model_manager import translate_text

        # No direct sv->de pair available
        mock_pkg.get_available_packages.return_value = [
            _make_package("sv", "en"),
            _make_package("en", "de"),
        ]

        mock_trans_sv_en = MagicMock()
        mock_trans_sv_en.translate.return_value = "Hello"
        mock_trans_en_de = MagicMock()
        mock_trans_en_de.translate.return_value = "Hallo"

        mock_load.side_effect = lambda src, tgt: (
            mock_trans_sv_en if (src, tgt) == ("sv", "en") else mock_trans_en_de
        )

        result = translate_text("Hej", "sv", "de")
        assert result == "Hallo"

        # Should have installed both legs
        assert mock_ensure.call_count == 2
        mock_ensure.assert_any_call("sv", "en")
        mock_ensure.assert_any_call("en", "de")

    @patch("app.model_manager._load_model")
    @patch("app.model_manager.ensure_installed")
    @patch("argostranslate.package")
    def test_direct_translation(self, mock_pkg, mock_ensure, mock_load):
        from app.model_manager import translate_text

        mock_pkg.get_available_packages.return_value = [
            _make_package("en", "sv"),
        ]

        mock_trans = MagicMock()
        mock_trans.translate.return_value = "Hej"
        mock_load.return_value = mock_trans

        result = translate_text("Hello", "en", "sv")
        assert result == "Hej"
        mock_ensure.assert_called_once_with("en", "sv")
