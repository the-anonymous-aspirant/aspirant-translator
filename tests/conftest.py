import sys
import pytest
from unittest.mock import patch, MagicMock

# Inject mock argostranslate modules so lazy imports resolve without the real package
_mock_argos = MagicMock()
sys.modules.setdefault("argostranslate", _mock_argos)
sys.modules.setdefault("argostranslate.package", _mock_argos.package)
sys.modules.setdefault("argostranslate.translate", _mock_argos.translate)
sys.modules.setdefault("argostranslate.settings", _mock_argos.settings)

from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def mock_model_manager():
    with patch("app.routes.model_manager") as mock_mm:
        yield mock_mm
