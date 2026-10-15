from lead_pipeline.llm import FakeProvider, heuristic_analyze
from lead_pipeline.schema import LeadRecord


def test_heuristic_categories(records: list[LeadRecord]) -> None:
    categories = [heuristic_analyze(r).category for r in records]
    assert categories == ["запись", "цена", "жалоба", "партнёрство", "спам"]


def test_heuristic_fields(records: list[LeadRecord]) -> None:
    booking = heuristic_analyze(records[0])
    assert booking.fields.name == "Олег"
    assert booking.fields.phone == "+79130000021"
    assert booking.fields.service == "замена масла"
    assert booking.fields.desired_date == "завтра утром"
    assert booking.urgency == "средняя"

    price = heuristic_analyze(records[1])
    assert price.fields.budget == 3000
    assert price.fields.service == "шиномонтаж"
    assert price.fields.name == "Марина"

    complaint = heuristic_analyze(records[2])
    assert complaint.urgency == "высокая"
    assert complaint.fields.phone == "+79130000067"

    partner = heuristic_analyze(records[3])
    assert partner.urgency == "низкая"
    assert partner.fields.name == "Анна Ким"
    assert partner.fields.service is None

    spam = heuristic_analyze(records[4])
    assert spam.urgency == "низкая"
    assert spam.fields.name is None


def test_fake_provider_is_deterministic(records: list[LeadRecord], prompt) -> None:
    provider = FakeProvider()
    first = [provider.analyze(r, prompt) for r in records]
    second = [provider.analyze(r, prompt) for r in records]
    assert first == second
    assert provider.calls == 10
