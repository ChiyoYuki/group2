"""Verify the browser-facing adapter against the migrated database."""

import json
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from dream_journey.database import transaction
from dream_journey.services import ProjectService
from dream_journey.web import ArchiveServer
from examples.dataset_import import import_dataset
from examples.import_miao import MEDIA, import_project
from examples.registry import BACKEND, get_dataset
from examples.seed import seed_database


@pytest.fixture
def web_server(engine):
    with ArchiveServer(
        ("127.0.0.1", 0),
        engine,
        cors_origins={"http://localhost:5173"},
        media_root=BACKEND / "media",
        static_root=BACKEND.parent / "frontend",
        mounts={"/demo-resources": BACKEND / "demo-resources"},
    ) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}"
        finally:
            server.shutdown()
            thread.join(timeout=5)


def get_json(base, path):
    with urlopen(base + path, timeout=5) as response:
        return json.load(response)


def test_browser_api_reads_database_filters_and_full_detail(web_server, factory):
    with transaction(factory) as session:
        seed_database(session)
    catalog = get_json(web_server, "/api/catalog")
    assert len(catalog["themes"]) == 7
    assert len(catalog["cohorts"]) == 3
    page = get_json(web_server, "/api/projects?theme=ecology")
    assert page["total"] == 1
    detail = get_json(web_server, "/api/projects/" + page["items"][0]["slug"])
    assert detail["is_demo"] is True
    assert len(detail["journey_entries"]) == 2
    assert detail["resources"][0]["type"]["code"] == "report"
    assert detail["resources"][0]["journey_entry_id"] in {
        entry["id"] for entry in detail["journey_entries"]
    }
    assert detail["published_at"].endswith("+00:00")
    overview = get_json(web_server, "/api/overview")
    assert overview["published_projects"] == 3
    assert overview["real_impact"]["project_count"] == 0


def test_api_hides_draft_and_archived_projects(web_server, factory, complete_project):
    with transaction(factory) as session:
        complete_project(session, slug="private-draft")
        archived = complete_project(session, slug="private-archived")
        ProjectService(session).publish(archived.id)
        ProjectService(session).archive(archived.id)
    assert get_json(web_server, "/api/projects")["items"] == []
    for slug in ("private-draft", "private-archived"):
        with pytest.raises(HTTPError) as error:
            get_json(web_server, "/api/projects/" + slug)
        assert error.value.code == 404


def test_invalid_parameters_return_useful_http_errors(web_server):
    for query in ("page=0", "page_size=101", "cohort=invalid", "featured=invalid"):
        with pytest.raises(HTTPError) as error:
            get_json(web_server, "/api/projects?" + query)
        assert error.value.code == 400
        assert "error" in json.load(error.value)


def test_static_files_and_resources_are_served_without_exposing_repository(web_server):
    for path, expected_type in (
        ("/", "text/html"),
        ("/app.js", "text/javascript"),
        ("/demo-resources/wetland-report.md", "text/markdown"),
    ):
        with urlopen(web_server + path, timeout=5) as response:
            assert response.status == 200
            assert response.headers.get_content_type() == expected_type
    with urlopen(Request(web_server + "/", method="HEAD"), timeout=5) as response:
        assert response.read() == b""
        assert int(response.headers["Content-Length"]) > 0
    for path in ("/.env", "/sql/001_initial.sql", "/demo-resources/%2e%2e/pyproject.toml"):
        with pytest.raises(HTTPError) as error:
            urlopen(web_server + path, timeout=5)
        assert error.value.code == 404


def test_versioned_api_exposes_sections_and_preserves_legacy_routes(web_server, factory):
    with transaction(factory) as session:
        import_project(session)
    health = get_json(web_server, "/api/v1/health")
    assert health == {"status": "ok", "api_version": 1, "database_revision": "0005"}
    detail = get_json(web_server, "/api/v1/projects/miao-culture-needlework")
    assert detail["dataset"]["version"] == 2
    assert len(detail["sections"]) == 10
    assert detail["sections"][0]["media"][-1]["resource"]["is_ai_generated"]
    sections = get_json(web_server, "/api/v1/projects/miao-culture-needlework/sections")
    assert sections["sections"] == detail["sections"]
    legacy = get_json(web_server, "/api/projects/miao-culture-needlework")
    assert legacy == detail


def test_audio_media_supports_seekable_byte_ranges_and_head(web_server):
    original = (MEDIA / "narration-01.mp3").read_bytes()
    path = web_server + "/media/miao-culture/narration-01.mp3"
    for header, expected in (
        ("bytes=0-15", original[:16]),
        ("bytes=16-", original[16:]),
        ("bytes=-8", original[-8:]),
        ("bytes=0-999999999", original),
    ):
        with urlopen(Request(path, headers={"Range": header}), timeout=5) as response:
            assert response.status == 206
            assert response.headers["Accept-Ranges"] == "bytes"
            assert response.headers.get_content_type() == "audio/mpeg"
            assert int(response.headers["Content-Length"]) == len(expected)
            assert response.headers["Content-Range"].endswith(f"/{len(original)}")
            assert response.read() == expected
    with urlopen(Request(path, method="HEAD"), timeout=5) as response:
        assert response.status == 200 and response.read() == b""
        assert int(response.headers["Content-Length"]) == len(original)


def test_invalid_media_ranges_return_416(web_server):
    path = web_server + "/media/miao-culture/narration-01.mp3"
    for value in ("bytes=999999999-", "bytes=3-1", "bytes=-0", "bytes=-", "bytes=1-2,4-5"):
        with pytest.raises(HTTPError) as error:
            urlopen(Request(path, headers={"Range": value}), timeout=5)
        assert error.value.code == 416
        assert error.value.headers["Content-Range"].startswith("bytes */")


def test_cors_preflight_and_api_media_headers(web_server):
    origin = "http://localhost:5173"
    preflight = Request(
        web_server + "/api/v1/projects",
        method="OPTIONS",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Range",
        },
    )
    with urlopen(preflight, timeout=5) as response:
        assert response.status == 204
        assert response.headers["Access-Control-Allow-Origin"] == origin
        assert "Range" in response.headers["Access-Control-Allow-Headers"]
    for path in ("/api/v1/health", "/media/miao-culture/narration-01.mp3"):
        with urlopen(Request(web_server + path, headers={"Origin": origin}), timeout=5) as response:
            assert response.headers["Access-Control-Allow-Origin"] == origin
            assert "Content-Range" in response.headers["Access-Control-Expose-Headers"]
    with pytest.raises(HTTPError) as error:
        urlopen(
            Request(
                web_server + "/api/v1/health",
                method="OPTIONS",
                headers={"Origin": "https://not-allowed.example"},
            ),
            timeout=5,
        )
    assert error.value.code == 403
    with urlopen(
        Request(web_server + "/api/v1/health", headers={"Origin": "https://not-allowed.example"}),
        timeout=5,
    ) as response:
        assert response.headers.get("Access-Control-Allow-Origin") is None


def test_second_project_api_exposes_documents_and_tables(web_server, factory):
    with transaction(factory) as session:
        import_project(session)
        import_dataset(session, get_dataset("dangar-old-town"))
    page = get_json(web_server, "/api/v1/projects?dataset=dangar-old-town")
    assert page["total"] == 1
    detail = get_json(web_server, "/api/v1/projects/" + page["items"][0]["slug"])
    assert detail["short_title"] == "古城里的马，也要“吃饭”吗？"
    assert len(detail["sections"]) == 11
    resources = {
        resource["import_key"].split(":", 1)[1]: resource for resource in detail["resources"]
    }
    assert len(resources["knowledge-status.csv"]["structured_data"]["rows"]) == 5
    assert "服务区" in resources["discovery-card.md"]["content_text"]
    for name, expected in (("discovery-card.md", "text/markdown"), ("comparison.csv", "text/csv")):
        with urlopen(web_server + "/media/dangar-old-town/" + name, timeout=5) as response:
            assert response.status == 200 and response.headers.get_content_type() == expected
            assert len(response.read()) > 0
