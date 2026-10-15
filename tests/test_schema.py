import pytest
from pydantic import ValidationError

from lead_pipeline.schema import CATEGORIES, LeadAnalysis, LeadFields, LeadRecord, normalize_phone


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("+7 913 000-00-21", "+79130000021"),
        ("8 (913) 000 00 21", "+79130000021"),
        ("89130000021", "+79130000021"),
        ("913 000 00 21", "+79130000021"),
        ("12345", None),
        ("", None),
    ],
)
def test_normalize_phone(raw: str, expected: str | None) -> None:
    assert normalize_phone(raw) == expected


def test_json_schema_constrains_category_and_nullable_fields() -> None:
    schema = LeadAnalysis.json_schema()
    assert set(schema["properties"]["category"]["enum"]) == set(CATEGORIES)
    assert "fields" in schema["properties"]
    fields_schema = schema["$defs"]["LeadFields"]["properties"]
    assert {"name", "phone", "service", "desired_date", "budget"} <= set(fields_schema)


def test_model_rejects_unknown_category() -> None:
    with pytest.raises(ValidationError):
        LeadAnalysis(category="прочее", urgency="низкая", summary="x", fields=LeadFields())


def test_fields_normalize_phone_on_validation() -> None:
    fields = LeadFields(phone="8 913 000-00-21", budget=5000)
    assert fields.phone == "+79130000021"


def test_record_roundtrip_and_prompt_text() -> None:
    record = LeadRecord.from_dict({"id": 7, "source": "email", "subject": "Тема", "text": "Текст", "extra_field": 1})
    assert record.id == "7"
    assert record.extra == {"extra_field": 1}
    assert record.to_dict()["extra_field"] == 1
    assert "Тема: Тема" in record.as_prompt_text()
    assert record.as_prompt_text().endswith("Текст:\nТекст")
