"""Провайдеры анализа заявок.

* ``AnthropicProvider`` — Claude через официальный SDK ``anthropic``. Ответ запрашивается
  как structured output по Pydantic-схеме ``LeadAnalysis`` (``client.messages.parse``),
  поэтому JSON гарантированно соответствует схеме: категория только из списка, поля
  либо значение, либо ``null``.
* ``FakeProvider`` — детерминированная эвристика на ключевых словах и регулярных
  выражениях. Нужна для тестов, CI и демонстрации без ключа API. Это именно
  заглушка: её точность на «золотом» наборе показывает нижнюю планку, а не качество
  модели.

Подход к извлечению полей (схема как «инструмент», который модель обязана
заполнить) взят из Anthropic Cookbook ``tool_use/extracting_structured_json.ipynb``
(MIT) и переведён на structured outputs.
"""

from __future__ import annotations

import logging
import re
from typing import Protocol

from .config import DEFAULT_MODEL, Settings
from .prompts import Prompt
from .schema import LeadAnalysis, LeadFields, LeadRecord, normalize_phone

log = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """Ошибка провайдера: сеть, лимиты, отказ модели, неверный ключ."""


class Provider(Protocol):
    name: str
    model: str

    def analyze(self, record: LeadRecord, prompt: Prompt) -> LeadAnalysis: ...


class AnthropicProvider:
    """Claude с structured outputs."""

    name = "anthropic"

    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL, max_tokens: int = 2048) -> None:
        import anthropic

        self._anthropic = anthropic
        # api_key=None — SDK возьмёт ANTHROPIC_API_KEY из окружения.
        self._client = anthropic.Anthropic(api_key=api_key, max_retries=3, timeout=90.0)
        self.model = model
        self.max_tokens = max_tokens

    def analyze(self, record: LeadRecord, prompt: Prompt) -> LeadAnalysis:
        try:
            response = self._client.messages.parse(
                model=self.model,
                max_tokens=self.max_tokens,
                system=prompt.text,
                messages=[{"role": "user", "content": record.as_prompt_text()}],
                output_format=LeadAnalysis,
                # Классификация короткого текста — минимального усилия достаточно
                # (на Claude Haiku 5.5 thinking включён по умолчанию, effort им управляет).
                output_config={"effort": "low"},
            )
        except self._anthropic.APIConnectionError as exc:
            raise LLMError(f"нет связи с API: {exc}") from exc
        except self._anthropic.APIStatusError as exc:
            raise LLMError(f"ошибка API {exc.status_code}: {exc.message}") from exc

        if response.stop_reason == "refusal":
            raise LLMError(f"модель отказалась обрабатывать текст ({response.stop_details})")
        if response.parsed_output is None:
            raise LLMError(f"структурированный ответ не получен (stop_reason={response.stop_reason})")
        return response.parsed_output


# ---------------------------------------------------------------------------
# Эвристическая заглушка
# ---------------------------------------------------------------------------

_KEYWORDS: dict[str, tuple[str, ...]] = {
    "жалоба": (
        "жалоб", "претенз", "недоволь", "верните деньги", "вернуть деньги", "возврат денег", "безобраз",
        "ужас", "кошмар", "обман", "испорт", "хуже", "не починил", "повторно", "после вашего", "после ремонта",
        "груб", "нахамил", "потерял", "поцарапа", "не сделали", "так и не", "обещали", "сорвали", "задержали",
        "некачествен", "брак", "переделат", "разочарован", "отвратитель", "напишу отзыв", "роспотребнадзор",
        "не вернули", "требую", "жду объяснений", "так нельзя", "не приняли", "примите меры", "принять меры",
    ),
    "партнёрство": (
        "сотрудничеств", "партнёр", "партнер", "поставщик", "поставк", "оптов", "дилер", "дистрибьют",
        "коммерческое предложение", "реклам", "размест", "размещен", "франшиз", "аренд", "страховой агент",
        "взаимовыгодн", "для вашего автосервиса", "вашему автосервису", "наша компания", "ооо «", "ооо \"",
        "прайс-лист для", "условия для сервисов", "спецуслови", "совместн", "агентство", "представляю",
    ),
    "спам": (
        "рассылк", "кредит", "займ", "криптовалют", "биткоин", "заработ", "выигр", "приз", "продвижени",
        "seo", "подписчик", "казино", "инвестиц", "ставк", "перейдите по ссылке", "http://", "https://",
        "отпиш", "только сегодня", "эксклюзивное предложение", "миллион", "гарантированный доход",
        "пассивный доход", "% в месяц", "дорогой друг", "уважаемый клиент банка", "срочно подтвердите",
        "вы выбраны", "отзывов", "бесплатно",
    ),
    "запись": (
        "запис", "запиш", "приехать", "подъехать", "заехать", "забронир", "свободно", "окошк", "примите",
        "принять", "когда можно", "можно завтра", "можно сегодня", "хочу приехать", "готов приехать",
        "на какое время", "поставьте меня", "приеду",
    ),
    "цена": (
        "сколько стоит", "стоимость", "цена", "цены", "расценк", "прайс", "почём", "по чем", "обойд",
        "сколько будет стоить", "сколько возьм", "во сколько", "сколько стоят", "нормо-час", "скидк",
    ),
}

_HIGH_URGENCY = (
    "срочно", "сегодня", "немедленно", "как можно скорее", "не заводится", "не на ходу", "отказали тормоза",
    "тормоза не", "течёт", "течет", "дым", "застрял", "посреди дороги", "эвакуатор", "прямо сейчас",
)
_LOW_URGENCY = ("просто интересуюсь", "на будущее", "не срочно", "когда-нибудь", "в перспективе", "сравниваю")

_SERVICES: tuple[tuple[str, str], ...] = (
    ("хранени[ея] шин", "хранение шин"),
    ("хранение", "хранение шин"),
    ("замен[аеуы]? масл", "замена масла"),
    ("масл", "замена масла"),
    ("шиномонтаж", "шиномонтаж"),
    ("переобу", "шиномонтаж"),
    ("балансировк", "шиномонтаж"),
    (r"\bшин[ыуа]?\b", "шиномонтаж"),
    ("колес", "шиномонтаж"),
    ("диагностик", "диагностика"),
    ("развал", "развал-схождение"),
    ("сход-развал", "развал-схождение"),
    ("кондиционер", "заправка кондиционера"),
    ("фреон", "заправка кондиционера"),
    ("колодк", "замена колодок"),
    ("тормоз", "замена колодок"),
    ("грм", "замена ГРМ"),
    ("подвеск", "ремонт подвески"),
    ("аккумулятор", "замена аккумулятора"),
    ("свеч", "замена свечей"),
    ("сцеплен", "ремонт сцепления"),
    ("предпродаж", "проверка перед покупкой"),
    ("перед покупкой", "проверка перед покупкой"),
    ("электрик", "ремонт электрики"),
    ("обогрев", "ремонт электрики"),
    ("кузов", "кузовной ремонт"),
    ("покрас", "покраска"),
    (r"\bто\b", "ТО"),
    ("техобслуж", "ТО"),
    ("техническое обслуживание", "ТО"),
    ("плановое обслуживание", "ТО"),
    ("стук", "ремонт подвески"),
)

_FIRST_NAMES = frozenset(
    """
    Алексей Марина Дмитрий Ольга Сергей Наталья Игорь Елена Андрей Татьяна Павел Ирина Виктор Анна Роман
    Светлана Олег Юлия Константин Вера Иван Мария Михаил Екатерина Николай Александр Александра Максим
    Дарья Евгений Евгения Владимир Анастасия Артём Артем Кирилл Ксения Денис Галина Валентина Пётр Петр
    """.split()
)
_NOT_NAMES = frozenset(
    """
    телефон тел номер звоните спасибо здравствуйте добрый прошу хочу можно машина автомобиль услуга
    сообщение имя заявка срочно сегодня завтра
    """.split()
)

_PHONE_RE = re.compile(r"(?:\+7|\b8|\b7)[\s\-(]*\d{3}[\s\-)]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}\b")
_NAME_RES = (
    re.compile(r"[Мм]еня зовут\s+([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?)"),
    re.compile(r"(?:^|\n)\s*Имя:\s*([^\n]+)"),
    re.compile(r"(?:^|[.!?,]\s+|\n)(?:[Ээ]то|[Яя])\s+([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?)(?=[,.!\s]|$)"),
    re.compile(
        r"(?:С уважением|Спасибо|Жду ответа|Заранее спасибо)[,!.]?\s*\n?\s*([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?)(?=[,.\s]|$)"
    ),
    re.compile(r"(?:Менеджер|Директор|Руководитель|Представитель|Администратор)\s+([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?)"),
    re.compile(r"([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?)[,.]?\s*(?:\+7|8)[\s\-(]*\d{3}"),
    re.compile(r"(?:^|\n)[—\-–]\s*([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?)\s*$", re.MULTILINE),
)
_WORD_RE = re.compile(r"[А-ЯЁ][а-яё]+")
_MONTHS = "января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря"
_DATE_RE = re.compile(
    r"(?:(?:после)?завтра|сегодня|(?:в|на|во)\s+(?:понедельник|вторник|среду|четверг|пятницу|субботу|воскресенье)|"
    r"на\s+(?:этих\s+)?выходных|на\s+(?:этой|следующей|след\.?)\s+неделе|в\s+ближайшие\s+дни|на\s+днях|"
    r"\b\d{1,2}[./]\d{1,2}(?:[./]\d{2,4})?\b|\b\d{1,2}\s+(?:" + _MONTHS + r")\b)"
    r"(?:\s*,?\s*(?:утром|вечером|днём|днем|после\s+обеда|в\s+первой\s+половине\s+дня|после\s+\d{1,2}(?::\d{2})?|"
    r"в\s+\d{1,2}(?::\d{2})?|к\s+\d{1,2}(?::\d{2})?|до\s+\d{1,2}(?::\d{2})?))?",
    re.IGNORECASE,
)
_BUDGET_RES = (
    re.compile(r"(\d{1,3}(?:[\s ]\d{3})+|\d{3,6})\s*(?:руб|р\.|₽|рублей|рубл)", re.IGNORECASE),
    re.compile(r"(\d{1,3}(?:[.,]\d)?)\s*(?:тыс|тысяч|к\b)", re.IGNORECASE),
    re.compile(r"бюджет[^\d\n]{0,20}(\d{1,3}(?:[\s ]\d{3})+|\d{3,6})", re.IGNORECASE),
)


def _find_service(text: str) -> str | None:
    lowered = text.lower()
    for pattern, service in _SERVICES:
        if re.search(pattern, lowered):
            return service
    return None


def _find_name(text: str) -> str | None:
    for pattern in _NAME_RES:
        match = pattern.search(text)
        if match:
            name = match.group(1).strip().strip(".,!")
            first = name.split()[0].lower()
            if first not in _NOT_NAMES and name != "-":
                return name
    # Запасной вариант: первое слово из словаря имён, возможно с фамилией после него.
    words = _WORD_RE.findall(text)
    for i, word in enumerate(words):
        if word in _FIRST_NAMES:
            following = words[i + 1] if i + 1 < len(words) else None
            if following and following not in _FIRST_NAMES and following.lower() not in _NOT_NAMES and \
                    re.search(re.escape(word) + r"\s+" + re.escape(following), text):
                return f"{word} {following}"
            return word
    return None


def _find_budget(text: str) -> int | None:
    lowered = text.lower()
    for i, pattern in enumerate(_BUDGET_RES):
        match = pattern.search(lowered)
        if not match:
            continue
        raw = match.group(1).replace(" ", "").replace(" ", "").replace(",", ".")
        try:
            value = float(raw)
        except ValueError:
            continue
        if i == 1:
            value *= 1000
        if 100 <= value <= 5_000_000:
            return int(value)
    return None


def _score(lowered: str, category: str) -> int:
    return sum(1 for kw in _KEYWORDS[category] if kw in lowered)


def _looks_like_gibberish(text: str) -> bool:
    cyrillic_words = re.findall(r"[а-яё]{4,}", text.lower())
    return len(cyrillic_words) < 3


def heuristic_analyze(record: LeadRecord) -> LeadAnalysis:
    """Правила вместо модели: категория по ключевым словам, поля по регулярным выражениям."""
    text = f"{record.subject or ''}\n{record.text}"
    lowered = text.lower().replace("ё", "е")

    scores = {cat: _score(lowered, cat) for cat in _KEYWORDS}
    if scores["жалоба"] >= 1:
        category = "жалоба"
    elif scores["партнёрство"] >= 1 and scores["партнёрство"] >= scores["запись"]:
        category = "партнёрство"
    elif scores["спам"] >= 2 or (scores["спам"] >= 1 and scores["запись"] + scores["цена"] == 0):
        category = "спам"
    elif scores["запись"] >= 1:
        category = "запись"
    elif scores["цена"] >= 1:
        category = "цена"
    elif _looks_like_gibberish(text):
        category = "спам"
    else:
        category = "запись" if _DATE_RE.search(text) else "цена"

    if category == "жалоба" or any(kw in lowered for kw in _HIGH_URGENCY):
        urgency = "высокая"
    elif category in ("партнёрство", "спам") or any(kw in lowered for kw in _LOW_URGENCY):
        urgency = "низкая"
    else:
        urgency = "средняя"
    if category == "спам":
        urgency = "низкая"

    phone_match = _PHONE_RE.search(text)
    date_match = _DATE_RE.search(text)
    fields = LeadFields(
        name=_find_name(text) if category != "спам" else None,
        phone=normalize_phone(phone_match.group(0)) if phone_match else None,
        service=_find_service(text) if category not in ("спам", "партнёрство") else None,
        desired_date=date_match.group(0).strip() if date_match and category in ("запись", "цена") else None,
        budget=_find_budget(text) if category in ("запись", "цена") else None,
    )
    lines = [ln.strip() for ln in record.text.strip().splitlines() if ln.strip()]
    message = next((ln.split(":", 1)[1].strip() for ln in lines if ln.lower().startswith("сообщение:")), None)
    summary = f"{category}: {(message or (lines[0] if lines else ''))[:120]}"
    return LeadAnalysis(category=category, urgency=urgency, summary=summary, fields=fields)


class FakeProvider:
    """Заглушка: вызывает ``heuristic_analyze``; ошибки можно подмешать для тестов."""

    name = "fake"
    model = "rules"

    def __init__(self, fail_ids: set[str] | None = None) -> None:
        self.fail_ids = fail_ids or set()
        self.calls = 0

    def analyze(self, record: LeadRecord, prompt: Prompt) -> LeadAnalysis:
        self.calls += 1
        if record.id in self.fail_ids:
            raise LLMError(f"искусственная ошибка для {record.id}")
        return heuristic_analyze(record)


def create_provider(settings: Settings, override: str | None = None) -> Provider:
    """``fake`` | ``anthropic`` | ``auto`` (Claude при наличии ключа, иначе заглушка)."""
    choice = (override or settings.llm_provider or "auto").lower()
    if choice == "fake":
        return FakeProvider()
    if choice == "anthropic":
        if not settings.anthropic_api_key:
            raise LLMError("LLM_PROVIDER=anthropic, но ANTHROPIC_API_KEY не задан")
        return AnthropicProvider(api_key=settings.anthropic_api_key, model=settings.anthropic_model)
    if choice == "auto":
        if settings.anthropic_api_key:
            return AnthropicProvider(api_key=settings.anthropic_api_key, model=settings.anthropic_model)
        log.warning("ANTHROPIC_API_KEY не задан — используется эвристическая заглушка вместо Claude")
        return FakeProvider()
    raise LLMError(f"Неизвестный провайдер: {choice!r}")
