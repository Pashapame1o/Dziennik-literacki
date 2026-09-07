from fastapi.testclient import TestClient

from diary.app.main import create_app


def test_authors_endpoint_reports_corpus_and_index_status():
    client = TestClient(create_app())
    authors = client.get("/api/authors").json()

    dostoevsky = next(a for a in authors if a["slug"] == "dostoevsky")
    assert "has_index" in dostoevsky
    assert "has_corpus" in dostoevsky
    # ships with no corpus files by design (SPEC 4.1: no source texts in the repo)
    assert dostoevsky["has_corpus"] is False
    assert dostoevsky["has_index"] is False
