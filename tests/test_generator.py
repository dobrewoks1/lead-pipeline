from lead_pipeline.generator import generate
from lead_pipeline.schema import CATEGORIES, SOURCES


def test_generate_is_deterministic_and_valid() -> None:
    records, labels = generate(n=60, seed=7)
    again, _ = generate(n=60, seed=7)
    assert records == again
    assert len(records) == len(labels) == 60
    assert len({r["id"] for r in records}) == 60
    for record, label in zip(records, labels):
        assert record["id"] == label["id"]
        assert record["source"] in SOURCES
        assert record["text"].strip()
        assert label["category"] in CATEGORIES
        assert label["urgency"] in ("низкая", "средняя", "высокая")
        if label["phone"]:
            assert label["phone"].startswith("+7") and len(label["phone"]) == 12


def test_all_categories_present_in_sample() -> None:
    _, labels = generate(n=80, seed=42)
    assert {l["category"] for l in labels} == set(CATEGORIES)
