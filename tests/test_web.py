from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("multipart")

from fastapi.testclient import TestClient

from co_extract.extractors import RulesExtractor
from co_extract.pipeline import ChangeOrderPipeline
from co_extract.schema import ExtractionResult
from co_extract.web import MAX_UPLOAD_BYTES, create_app
from tests.conftest import SAMPLES


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(ChangeOrderPipeline([RulesExtractor()])))


def test_page_and_health(client: TestClient) -> None:
    page = client.get("/")
    assert page.status_code == 200 and "Change Order Extractor" in page.text
    assert client.get("/health").json() == {"status": "ok"}
    assert "change_order" in client.get("/api/schema").json()["properties"]


def test_extract_text(client: TestClient) -> None:
    text = (SAMPLES / "co_001_clean.txt").read_text(encoding="utf-8")
    response = client.post("/api/extract-text", json={"text": text})
    result = ExtractionResult.model_validate(response.json())
    assert result.change_order.change_order_number.value == "CO-014"
    assert not result.needs_review


def test_extract_pdf_upload_uses_the_client_file_name_only_as_a_label(client: TestClient) -> None:
    pdf = (SAMPLES / "co_006_pdf.pdf").read_bytes()
    response = client.post("/api/extract", files={"file": ("../../evil name.pdf", pdf)})
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "evil name.pdf"
    assert body["change_order"]["change_order_number"]["value"] == "CO-008"


def test_rejects_empty_text_bad_type_and_oversized_files(client: TestClient) -> None:
    assert client.post("/api/extract-text", json={"text": "  "}).status_code == 422
    assert client.post("/api/extract", files={"file": ("x.exe", b"MZ")}).status_code == 415
    big = b"x" * (MAX_UPLOAD_BYTES + 1)
    assert client.post("/api/extract", files={"file": ("big.txt", big)}).status_code == 413


def test_unreadable_upload_is_a_clean_422_without_server_paths(client: TestClient) -> None:
    response = client.post("/api/extract", files={"file": ("empty.txt", b"hi")})
    assert response.status_code == 422
    assert "/tmp" not in response.json()["detail"]
