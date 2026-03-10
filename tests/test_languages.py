def test_list_languages(client, mock_model_manager):
    mock_model_manager.get_available_pairs.return_value = {
        "languages": [
            {
                "code": "en",
                "name": "English",
                "targets": [
                    {"code": "sv", "installed": True},
                    {"code": "de", "installed": False},
                ],
            }
        ],
        "total_pairs": 2,
        "installed_pairs": 1,
    }

    resp = client.get("/languages")
    assert resp.status_code == 200
    data = resp.json()
    assert "languages" in data
    assert "total_pairs" in data
    assert "installed_pairs" in data
    assert len(data["languages"]) == 1
    assert data["languages"][0]["code"] == "en"


def test_install_already_installed(client, mock_model_manager):
    mock_model_manager.ensure_installed.return_value = False

    resp = client.post("/languages/install", json={
        "source_language": "en",
        "target_language": "sv",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "installed"
    assert "already" in data["message"].lower()


def test_install_new_pair(client, mock_model_manager):
    mock_model_manager.ensure_installed.return_value = True

    resp = client.post("/languages/install", json={
        "source_language": "en",
        "target_language": "de",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "installed"
    assert "downloaded" in data["message"].lower()


def test_install_unsupported_pair(client, mock_model_manager):
    from app.model_manager import UnsupportedPairError
    mock_model_manager.ensure_installed.side_effect = UnsupportedPairError("No package")
    mock_model_manager.UnsupportedPairError = UnsupportedPairError

    resp = client.post("/languages/install", json={
        "source_language": "en",
        "target_language": "zz",
    })
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "unsupported_language_pair"
