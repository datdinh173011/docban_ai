from app.knowledge_ingestion import chunk_text, validate_manifest


def test_chunking_preserves_article_heading() -> None:
    chunks = chunk_text("Điều 16. Thẩm quyền đăng ký khai sinh\nỦy ban nhân dân cấp xã thực hiện đăng ký khai sinh.")
    assert chunks[0].title.startswith("Điều 16")
    assert chunks[0].hierarchy_path[0]["label"].startswith("Điều 16")


def test_manifest_requires_citation_metadata() -> None:
    errors = validate_manifest({"document_code": "DOC", "procedure_code": "BIRTH_REGISTRATION", "source_file": "source.pdf", "source": {}})
    assert "source_missing:source_code" in errors


def test_manifest_rejects_unrecognized_procedure_fact() -> None:
    errors = validate_manifest({
        "document_code": "DOC",
        "procedure_code": "BIRTH_REGISTRATION",
        "source_file": "source.pdf",
        "source": {
            "source_code": "SOURCE",
            "source_type": "law",
            "title_vi": "Nguồn",
            "source_url": "https://example.test/source",
            "effective_from": "2020-01-01",
        },
        "procedure_facts": [{"fact_type": "unsafe_sql", "value": {"text": "Không hợp lệ"}}],
    })
    assert errors == ["procedure_fact_invalid:0"]
