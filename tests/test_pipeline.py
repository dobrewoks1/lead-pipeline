from lead_pipeline.llm import FakeProvider
from lead_pipeline.pipeline import process
from lead_pipeline.report import format_console_report, format_telegram_summary, summarize
from lead_pipeline.schema import LeadRecord


def test_process_keeps_order_and_captures_errors(records: list[LeadRecord], prompt) -> None:
    provider = FakeProvider(fail_ids={"T-3"})
    seen = []
    results = process(records, provider, prompt, workers=3, progress=lambda done, total, r: seen.append(done))
    assert [r.record.id for r in results] == [r.id for r in records]
    assert seen == [1, 2, 3, 4, 5]
    failed = results[2]
    assert not failed.ok and "искусственная ошибка" in failed.error
    assert all(r.ok for r in results if r.record.id != "T-3")
    assert all(r.prompt_version == prompt.version and r.provider == "fake" for r in results)


def test_summary_and_reports(records: list[LeadRecord], prompt) -> None:
    results = process(records, FakeProvider(), prompt, workers=1)
    summary = summarize(results)
    assert summary.total == 5 and summary.ok == 5 and summary.errors == 0
    assert summary.by_category["жалоба"] == 1
    assert [r.record.id for r in summary.urgent] == ["T-3"]
    assert summary.with_phone == 3

    console = format_console_report(results, "fake", prompt.version, ["out/leads.csv"])
    assert "Итого: 5 заявок" in console
    assert "Срочные обращения (1)" in console
    assert "out/leads.csv" in console

    tg = format_telegram_summary(results)
    assert tg.startswith("<b>Заявки за прогон: 5</b>")
    assert "T-3" in tg
