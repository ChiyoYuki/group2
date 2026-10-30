"""HTTP behavior tested with an empty migrated database and temporary media."""

import base64
import json
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from dream_journey.web import ArchiveServer


@pytest.fixture
def web_server(engine, tmp_path):
    media = tmp_path / "media"
    media.mkdir()
    (media / "clip.mp3").write_bytes(bytes(range(64)))
    with ArchiveServer(
        ("127.0.0.1", 0), engine, media_root=media, cors_origins={"http://localhost:5173"}
    ) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}"
        finally:
            server.shutdown()
            thread.join(timeout=5)


def test_empty_backend_exposes_api_without_loading_any_content_or_frontend(web_server):
    for path, expected in (
        ("/api/v1/health", {"status": "ok", "api_version": 1, "database_revision": "0006"}),
        ("/api/v1/projects", {"items": [], "total": 0, "page": 1, "page_size": 12}),
        ("/api/v1/catalog", {"themes": [], "cohorts": [], "resource_types": []}),
    ):
        with urlopen(web_server + path, timeout=5) as response:
            assert json.load(response) == expected
    with pytest.raises(HTTPError) as error:
        urlopen(web_server + "/", timeout=5)
    assert error.value.code == 404


def test_unknown_dataset_filter_is_an_empty_result(web_server):
    with urlopen(web_server + "/api/v1/projects?dataset=any-new-dataset", timeout=5) as response:
        assert json.load(response)["total"] == 0


def test_configured_media_root_supports_ranges_and_cors(web_server):
    request = Request(
        web_server + "/media/clip.mp3",
        headers={
            "Range": "bytes=4-10",
            "Origin": "http://localhost:5173",
        },
    )
    with urlopen(request, timeout=5) as response:
        assert response.status == 206
        assert response.read() == bytes(range(4, 11))
        assert response.headers["Content-Range"] == "bytes 4-10/64"
        assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
    with pytest.raises(HTTPError) as error:
        urlopen(web_server + "/media/%2e%2e/alembic.ini", timeout=5)
    assert error.value.code == 404


def test_register_login_and_publish_project_with_upload(web_server):
    def post(path, payload, token=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = Request(
            web_server + path,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        return urlopen(request, timeout=5)

    with post(
        "/api/v1/auth/register", {"username": "Demo_User", "password": "correct-horse"}
    ) as response:
        assert response.status == 201
        registered = json.load(response)
    assert registered["user"]["username"] == "demo_user"

    with pytest.raises(HTTPError) as error:
        post("/api/v1/auth/login", {"username": "demo_user", "password": "wrong-password"})
    assert error.value.code == 401

    with post(
        "/api/v1/auth/login", {"username": "demo_user", "password": "correct-horse"}
    ) as response:
        token = json.load(response)["token"]
    with post(
        "/api/v1/projects",
        {
            "title": "我的第一个项目",
            "summary": "一次简单的项目上传",
            "description": "项目详细说明",
            "file": {
                "name": "notes.txt",
                "content_base64": base64.b64encode(b"project notes").decode(),
            },
        },
        token,
    ) as response:
        assert response.status == 201
        project = json.load(response)
    assert project["status"] == "published"

    with urlopen(web_server + "/api/v1/projects", timeout=5) as response:
        projects = json.load(response)
    assert projects["total"] == 1
    assert projects["items"][0]["title"] == "我的第一个项目"
    with urlopen(web_server + project["resource_url"], timeout=5) as response:
        assert response.read() == b"project notes"
