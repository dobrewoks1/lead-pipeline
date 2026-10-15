# lead-pipeline

[![CI](https://github.com/dobrewoks1/lead-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/dobrewoks1/lead-pipeline/actions/workflows/ci.yml)

Входящие обращения в свободной форме (письма, заявки с сайта, сообщения из чата) → категория, срочность,
суть одной строкой и поля: имя, телефон, услуга, желаемая дата, бюджет → таблица CSV/XLSX, по желанию
сводка в Telegram и лист Google Sheets. Разбор делает Claude по строгой JSON-схеме, промпты лежат файлами
с версиями, качество меряется на размеченном наборе и держится порогом в тестах.

Показан на примере автосервиса «Вектор» (Омск). Клиенты, телефоны и компании в репозитории вымышленные.

## Результаты

| Набор | Провайдер | Промпт | Категории | Срочность | Поля: имя / телефон / услуга / дата / бюджет |
|---|---|---|---|---|---|
| golden, 30 обращений, размечены вручную | Claude Haiku 5.5 | v2 | **100 %** | 97 % | 100 / 100 / 93 / 80 / 97 % |
| golden, 30 | Claude Haiku 5.5 | v1 | 97 % | 93 % | 97 / 93 / 87 / 80 / 93 % |
| sample, 80 синтетических | Claude Haiku 5.5 | v2 | 97,5 % | 94 % | 98 / 91 / 99 / 89 / 99 % |
| golden, 30 | заглушка на правилах | — | 100 % | 93 % | 100 / 100 / 97 / 97 / 100 % |

Прогоны на Claude — 15.10.2026, `effort: low`, около 1,7 с на заявку в четыре потока. Переход с v1 на v2
(правила спорных случаев и примеры по каждой категории) убрал ошибку «вопрос по цене или запись» и поднял
точность полей. Цифры заглушки — нижняя планка: правила знают только слова, которые есть в синтетике;
ценность конвейера — в модели, которая понимает перефразировки.

Отчёт в консоли после прогона 80 заявок (сокращены только длинные строки):

```
Заявок: 80. Провайдер: anthropic (claude-haiku-5-5). Промпт: v2. Потоков: 4.
Итого: 80 заявок, обработано 80, ошибок 0 (провайдер anthropic, промпт v2, в среднем 1683 мс/заявку)
По категориям:
  запись на услугу      23  ██████░░░░░░░░░░░░░░
  вопрос по цене        21  █████░░░░░░░░░░░░░░░
  жалоба                12  ███░░░░░░░░░░░░░░░░░
  партнёрство           12  ███░░░░░░░░░░░░░░░░░
  спам                  12  ███░░░░░░░░░░░░░░░░░
По срочности:
  низкая                33  ████████░░░░░░░░░░░░
  средняя               30  ████████░░░░░░░░░░░░
  высокая               17  ████░░░░░░░░░░░░░░░░
Источники: chat — 32, email — 28, form — 20
Телефон извлечён: 52 из 80
Популярные услуги: шиномонтаж (8), ТО (8), замена масла (7), замена ГРМ (5), ремонт подвески (5)
Срочные обращения (17) — обработать в первую очередь:
  ! L-0001 [жалоба] Андрей Соколов, +79130000038: Андрей Соколов жалуется, что после шиномонтажа два дня назад загорелся чек…
  ! L-0012 [запись] Олег, +79130000086: Клиент на Toyota RAV4 2015 после удара о бордюр слышит стук в подвеске, хочет ремонт…
  ! L-0017 [запись] Ирина, +78913000062: Ирина просит срочно записать Kia Rio 2018 на замену масла в четверг в 10:00…
  ! L-0023 [жалоба] без имени, +79130000094: Клиент жалуется, что автосервис потерял его запасной ключ от Toyota Corolla 2012…
Файлы: out\leads.csv, out\leads.xlsx, out\summary.json
```

## Как устроено

```
data/*.jsonl ──► lead_pipeline.pipeline ──► Claude (structured outputs, JSON по схеме)
                        │                        │ без ключа: заглушка на правилах
                        ▼                        ▼
                 out/leads.csv  out/leads.xlsx  out/summary.json  → отчёт в консоли
                        └──► (опционально) сводка в Telegram, лист в Google Sheets
```

1. **Схема результата** — Pydantic-модель `LeadAnalysis`: `category` (запись | цена | жалоба | партнёрство |
   спам), `urgency` (низкая | средняя | высокая), `summary`, `fields` (имя, телефон `+7XXXXXXXXXX`, услуга,
   желаемая дата, бюджет в рублях или `null`).
2. **Промпты** — `prompts/lead_analysis.v1.md`, `v2.md` с frontmatter: определения категорий, правила спорных
   случаев, нормализация полей, changelog. Версия промпта пишется в каждую строку результата.
3. **Провайдеры** — Claude (`claude-haiku-5-5` по умолчанию) или детерминированная заглушка на ключевых
   словах и регулярных выражениях для тестов, CI и показа без ключа.
4. **Выгрузка** — CSV (UTF-8 с BOM, открывается в Excel) и XLSX с автофильтром, закреплённой шапкой,
   подсветкой срочности и листом «Сводка».
5. **Оценка** — `evals/golden.jsonl`, 30 обращений, размеченных вручную; тест считает точность категорий
   и срочности и печатает матрицу ошибок.
6. **Интеграции, выключены по умолчанию** — сводка в Telegram через Bot API (`NOTIFY_TELEGRAM=1`), лист
   Google Sheets через gspread (`GSHEETS_ENABLED=1`).

## Что здесь важно

- **Схема первична.** Модель не «возвращает JSON», а заполняет схему (`client.messages.parse`): не бывает
  лишних полей, неверных категорий и битого JSON, значит нет ветки «распарсить и починить».
- **Промпт — файл с версией.** Любую строку результата можно воспроизвести: известно, какой промпт и
  какая модель её сделали. Сравнение версий — одна команда.
- **Порог в тесте.** Изменил промпт — `pytest evals/` скажет, стало ли хуже. На заглушке идёт в CI,
  на Claude запускается `LEAD_EVAL_PROVIDER=anthropic pytest evals/`.
- **Ошибка на одной заявке не роняет прогон**: она попадает в поле `error` строки результата, остальные
  заявки обрабатываются параллельно с сохранением порядка.
- **XLSX сделан для менеджера**, а не для программиста: открыл, отфильтровал срочные, позвонил.

## Попробовать

```bash
git clone https://github.com/dobrewoks1/lead-pipeline.git
cd lead-pipeline
python -m venv .venv && .venv\Scripts\activate      # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env                                # ANTHROPIC_API_KEY — если есть
```

Прогон на 80 синтетических заявках: `python -m lead_pipeline run --input data/sample.jsonl --out out/`.
Без ключа конвейер предупредит и возьмёт заглушку; провайдер можно задать явно `--provider fake | anthropic`,
версию промпта — `--prompt v1`. Результат: `out/leads.csv`, `out/leads.xlsx`, `out/summary.json` и отчёт
в консоли.

Другие команды:

```bash
python -m lead_pipeline generate --n 100 --seed 7 --out data/my.jsonl --labels data/my.labels.jsonl
python -m lead_pipeline eval --provider anthropic              # точность на золотом наборе
python -m lead_pipeline eval --provider anthropic --prompt v1  # сравнить версии промптов
python -m lead_pipeline prompts                                # список версий
```

Тесты без сети и без ключей: `pytest`. Тест `evals/test_golden_accuracy.py` держит порог: категории ≥ 90 %,
срочность ≥ 80 %.

Docker (образ собирается и проверяется в CI): `docker build -t lead-pipeline .` и
`docker run --env-file .env -v %cd%/out:/app/out lead-pipeline`.

Что показать за три минуты — [docs/walkthrough.md](docs/walkthrough.md).

## Формат входа

JSON Lines, по одной заявке в строке:

```json
{"id": "L-0001", "source": "email", "received_at": "2026-10-05T17:01", "subject": "Запись на ТО", "text": "Добрый день! ..."}
```

Обязательны `id`, `source` (`email` | `form` | `chat`) и `text`; остальные поля переносятся в результат как есть.

## Устройство

```
lead_pipeline/
  schema.py      модели данных и JSON-схема      llm.py        Claude / заглушка
  prompts.py     загрузка версий промптов        pipeline.py   параллельная обработка
  export.py      CSV и XLSX                      report.py     сводка для консоли и Telegram
  notify.py      Telegram, Google Sheets         evalrun.py    точность и матрица ошибок
  generator.py   синтетические заявки            __main__.py   CLI
prompts/         lead_analysis.v1.md, v2.md, README.md
data/            sample.jsonl (80 заявок) + sample.labels.jsonl (разметка генератора)
evals/           golden.jsonl (30 примеров), test_golden_accuracy.py, README.md
tests/           pytest, 27 тестов, без сети
docs/            экскурсия за три минуты
```

Парный проект — [support-bot](https://github.com/dobrewoks1/support-bot): тот же вымышленный автосервис,
но бот отвечает клиентам в чате, а этот конвейер разбирает входящие заявки в таблицу.

## Что дальше

Планы — в [issues](../../issues): даты в календарный вид относительно `received_at`, Message Batches API
для тысяч заявок, склейка повторных обращений одного клиента.

## Как делалось

Собран в связке с Claude Code: схема, категории, правила спорных случаев, разметка золотого набора и
порог качества — мои; код, генератор синтетики и тесты написаны агентом по ним и проверены живыми прогонами.
Правила для агента в этом репозитории — [CLAUDE.md](CLAUDE.md).

## Источники

| Что взято | Откуда | Лицензия |
|---|---|---|
| Извлечение структурированных данных по JSON-схеме, переведено на structured outputs | [Anthropic Cookbook — tool_use/extracting_structured_json.ipynb](https://github.com/anthropics/anthropic-cookbook/blob/main/tool_use/extracting_structured_json.ipynb) | MIT |
| Классификация обращений: определения категорий с примерами в промпте, оценка точности и матрица ошибок | [Anthropic Cookbook — capabilities/classification/guide.ipynb](https://github.com/anthropics/anthropic-cookbook/blob/main/capabilities/classification/guide.ipynb) | MIT |
| Формат structured outputs (`messages.parse` + Pydantic) | [документация Anthropic](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) | — |

Код проекта — MIT, см. [LICENSE](LICENSE).

---

**In English.** LLM pipeline for inbound leads of a fictional car service: synthetic Russian emails, web-form
and chat messages are classified (booking / pricing / complaint / partnership / spam) with urgency, and contact
fields (name, phone, service, date, budget) are extracted by Claude via structured outputs against a Pydantic
schema. Results go to CSV/XLSX with an optional Telegram summary and Google Sheets export. Prompts are
versioned files; a 30-item hand-labeled golden set with an accuracy threshold guards quality (100 % categories
on Claude Haiku 5.5 with prompt v2). Works offline through a deterministic rule-based provider used by the
test suite. All data is fictional.
