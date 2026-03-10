import pytest


def test_translate_missing_text(client, mock_model_manager):
    resp = client.post("/translations", json={
        "text": "",
        "source_language": "en",
        "target_language": "sv",
    })
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "validation_error"


def test_translate_same_language(client, mock_model_manager):
    resp = client.post("/translations", json={
        "text": "Hello",
        "source_language": "en",
        "target_language": "en",
    })
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "validation_error"
    assert "different" in resp.json()["error"]["message"]


def test_translate_text_too_long(client, mock_model_manager):
    resp = client.post("/translations", json={
        "text": "x" * 5001,
        "source_language": "en",
        "target_language": "sv",
    })
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "validation_error"
    assert "maximum length" in resp.json()["error"]["message"]


def test_translate_success(client, mock_model_manager):
    mock_model_manager.translate_text.return_value = "Hej världen"

    resp = client.post("/translations", json={
        "text": "Hello world",
        "source_language": "en",
        "target_language": "sv",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["text"] == "Hello world"
    assert data["translated_text"] == "Hej världen"
    assert data["source_language"] == "en"
    assert data["target_language"] == "sv"
    assert data["characters"] == 11
    assert "processing_time_seconds" in data

    mock_model_manager.translate_text.assert_called_once_with(
        "Hello world", "en", "sv"
    )


def test_translate_unsupported_pair(client, mock_model_manager):
    from app.model_manager import UnsupportedPairError
    mock_model_manager.translate_text.side_effect = UnsupportedPairError("No package")
    mock_model_manager.UnsupportedPairError = UnsupportedPairError

    resp = client.post("/translations", json={
        "text": "Hello",
        "source_language": "en",
        "target_language": "zz",
    })
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "unsupported_language_pair"


def test_translate_download_failed(client, mock_model_manager):
    from app.model_manager import DownloadError
    mock_model_manager.translate_text.side_effect = DownloadError("Network error")
    mock_model_manager.DownloadError = DownloadError

    resp = client.post("/translations", json={
        "text": "Hello",
        "source_language": "en",
        "target_language": "sv",
    })
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "download_failed"


def test_translate_model_load_failed(client, mock_model_manager):
    from app.model_manager import ModelLoadError
    mock_model_manager.translate_text.side_effect = ModelLoadError("Load error")
    mock_model_manager.ModelLoadError = ModelLoadError

    resp = client.post("/translations", json={
        "text": "Hello",
        "source_language": "en",
        "target_language": "sv",
    })
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "model_load_failed"
