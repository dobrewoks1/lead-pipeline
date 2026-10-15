"""Генератор синтетических обращений для вымышленного автосервиса «Вектор» (Омск).

Все имена, телефоны (с кодом 000) и компании вымышлены. Генерация детерминирована
по ``seed``, поэтому ``data/sample.jsonl`` воспроизводим. Вместе с заявками можно
сохранить разметку (категория, срочность, поля) — она известна из шаблона и
пригодна для оценки качества конвейера на большом объёме.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from .schema import normalize_phone

NAMES = [
    "Алексей", "Марина", "Дмитрий", "Ольга", "Сергей", "Наталья", "Игорь", "Елена", "Андрей", "Татьяна",
    "Павел", "Ирина", "Виктор", "Анна", "Роман", "Светлана", "Олег", "Юлия", "Константин", "Вера",
]
FEMALE_NAMES = {"Марина", "Ольга", "Наталья", "Елена", "Татьяна", "Ирина", "Анна", "Светлана", "Юлия", "Вера"}
SURNAMES = ["Петров", "Смирнов", "Ким", "Соколов", "Орлов", "Лебедев", "Новиков", "Морозов", "Волков", "Козлов"]
CARS = [
    "Kia Rio 2018", "Hyundai Solaris 2016", "Lada Vesta 2020", "Toyota Corolla 2012", "Renault Logan 2015",
    "Skoda Octavia 2019", "Nissan Qashqai 2017", "Volkswagen Polo 2014", "Mazda 3 2013", "Ford Focus 2011",
    "Haval Jolion 2022", "Chery Tiggo 7 2023", "Lada Granta 2021", "Toyota RAV4 2015",
]
# (именительный падеж — он же каноническое название услуги, винительный падеж)
SERVICES: list[tuple[str, str]] = [
    ("замена масла", "замену масла"),
    ("шиномонтаж", "шиномонтаж"),
    ("диагностика", "диагностику"),
    ("развал-схождение", "развал-схождение"),
    ("заправка кондиционера", "заправку кондиционера"),
    ("замена колодок", "замену колодок"),
    ("ТО", "ТО"),
    ("ремонт подвески", "ремонт подвески"),
    ("замена ГРМ", "замену ГРМ"),
    ("хранение шин", "хранение шин"),
]
DATES = [
    "завтра", "сегодня после 18:00", "в субботу", "в субботу утром", "на выходных", "15 октября",
    "в пятницу вечером", "послезавтра", "на следующей неделе", "20.10", "в четверг в 10:00", "завтра утром",
]
BUDGETS = [3000, 5000, 8000, 10000, 15000, 20000]
BUDGET_FORMS = ["до {n} руб.", "бюджет около {n} рублей", "не больше {k} тыс.", "в пределах {n} руб", "рассчитываю на {n} ₽"]
COMPANIES = [
    "ООО «Масло-Опт»", "ТД «АвтоДеталь-Сибирь»", "ИП Вымышленный А. А.", "агентство «Реклама-55»",
    "сеть автомоек «Чистый кузов»", "компания «Шины-Логистик»",
]
PAST_DATES = ["Неделю назад", "В прошлую пятницу", "Три дня назад", "10 октября", "Позавчера"]

# Формы глаголов для мужского и женского рода: (м, ж).
VERBS = {
    "did": ("делал", "делала"),
    "signed_up": ("Записывался", "Записывалась"),
    "arrived": ("приехал", "приехала"),
    "lost": ("Потерял", "Потеряла"),
    "handed": ("сдавал", "сдавала"),
    "took": ("забрал", "забрала"),
    "ready": ("Готов", "Готова"),
}


@dataclass(frozen=True)
class Template:
    category: str
    urgency: str
    source: str
    subject: str | None
    text: str


# Плейсхолдеры: {name} {surname} {phone} {car} {service} {service_acc} {date} {budget}
# {budget_plain} {company} {date_past} и глаголы из VERBS. Разметка берётся из того,
# какие плейсхолдеры есть в шаблоне.
TEMPLATES: list[Template] = [
    # --- запись на услугу ---------------------------------------------------
    Template("запись", "средняя", "chat", None,
             "Здравствуйте! Хочу записаться на {service_acc}, машина {car}. Можно {date}? Меня зовут {name}, тел. {phone}"),
    Template("запись", "средняя", "form", "Заявка с сайта",
             "Имя: {name}\nТелефон: {phone}\nАвтомобиль: {car}\nУслуга: {service}\nСообщение: Хотелось бы приехать {date}. Подтвердите, пожалуйста, время."),
    Template("запись", "средняя", "email", "Запись на {service_acc}",
             "Добрый день!\n\nПрошу записать меня на {service_acc}. Автомобиль {car}. Удобно {date}. {budget}.\n\nС уважением,\n{name} {surname}\n{phone}"),
    Template("запись", "высокая", "chat", None,
             "Срочно! {car} барахлит, нужно сделать {service_acc}. Можно подъехать {date}? {phone}, {name}"),
    Template("запись", "средняя", "chat", None,
             "добрый день, это {name}. записывайте меня на {service_acc} {date}, {car}. номер {phone}"),
    Template("запись", "средняя", "form", "Запись онлайн",
             "Имя: {name} {surname}\nТелефон: {phone}\nУслуга: {service}\nСообщение: {car}, хочу приехать {date}, {budget}."),
    Template("запись", "высокая", "email", "Нужна помощь сегодня",
             "Здравствуйте. У меня {car}, после удара о бордюр что-то стучит, нужно сделать {service_acc}. Можно сегодня? {ready} приехать прямо сейчас.\n\n{name}, {phone}"),
    # --- вопрос по цене ------------------------------------------------------
    Template("цена", "средняя", "chat", None,
             "Подскажите, сколько стоит {service} на {car}? Если цена устроит, приеду {date}. {name}"),
    Template("цена", "средняя", "email", "Стоимость услуги: {service}",
             "Добрый день! Интересует стоимость услуги «{service}» для {car}. Сколько по времени займёт? {budget}.\n\nСпасибо,\n{name}"),
    Template("цена", "низкая", "chat", None,
             "Здравствуйте, просто интересуюсь на будущее: почём у вас {service}? Машина {car}."),
    Template("цена", "средняя", "form", "Вопрос по цене",
             "Имя: {name}\nТелефон: {phone}\nСообщение: Сколько будет стоить {service} с запчастями для {car}? {budget}."),
    Template("цена", "низкая", "email", "Прайс",
             "Здравствуйте! Пришлите, пожалуйста, расценки на {service_acc} и ТО для {car}. Планирую обслуживание в перспективе, пока сравниваю сервисы.\n\n{name} {surname}"),
    Template("цена", "средняя", "chat", None,
             "{service} для {car} — сколько стоит и есть ли скидка для постоянных клиентов? тел {phone}"),
    # --- жалоба ---------------------------------------------------------------
    Template("жалоба", "высокая", "email", "Претензия по заказ-наряду",
             "Здравствуйте. {date_past} {did} у вас {service_acc} ({car}), а сегодня загорелся чек и машина дёргается. Прошу переделать по гарантии или вернуть деньги. Заказ-наряд сохранил.\n\n{name} {surname}, {phone}"),
    Template("жалоба", "высокая", "chat", None,
             "После вашей работы — {service} на {car} — стук стал ещё хуже. Это безобразие, я за это заплатил {budget_plain} рублей! Жду звонка сегодня. {name}, {phone}"),
    Template("жалоба", "высокая", "form", "Жалоба",
             "Имя: {name}\nТелефон: {phone}\nСообщение: {signed_up} на {service_acc} {date}, {arrived}, а меня не приняли — «нет мастера». {lost} полдня. Хочу, чтобы разобрались."),
    Template("жалоба", "высокая", "email", "Недоволен обслуживанием",
             "Добрый день. {date_past} {handed} {car} на {service_acc}. Обещали за два часа, {took} через шесть, при этом в салоне остались грязные следы. Прошу принять меры и перезвонить.\n\nС уважением,\n{name} {surname}\n{phone}"),
    Template("жалоба", "высокая", "chat", None,
             "Вы потеряли мой запасной ключ, когда машина ({car}) была у вас в ремонте ({service}). Верните, пожалуйста, или компенсируйте. {phone}"),
    # --- партнёрство ------------------------------------------------------------
    Template("партнёрство", "низкая", "email", "Коммерческое предложение",
             "Добрый день!\n\n{company} предлагает вашему автосервису сотрудничество: поставка масел и фильтров со склада в Омске, отсрочка платежа 14 дней, спецусловия для сервисов.\n\nБуду рад обсудить. Менеджер {name} {surname}, {phone}"),
    Template("партнёрство", "низкая", "email", "Сотрудничество",
             "Здравствуйте! Мы — {company}. Предлагаем взаимовыгодное партнёрство: наши клиенты получают скидку у вас, ваши — у нас. Готовы обсудить условия на встрече.\n\n{name}, {phone}"),
    Template("партнёрство", "низкая", "chat", None,
             "Добрый день, {company}. Хотим разместить рекламу вашего сервиса у себя и наоборот. Кто у вас отвечает за партнёрство? {phone}"),
    Template("партнёрство", "низкая", "form", "Поставки запчастей",
             "Имя: {name}\nТелефон: {phone}\nСообщение: {company}, оптовые поставки тормозных колодок и дисков. Пришлём прайс-лист для сервисов, если интересно."),
    Template("партнёрство", "низкая", "email", "Аренда бокса",
             "Здравствуйте. Рассматриваете ли вы сдачу в аренду одного бокса под детейлинг по выходным? {company}, готовы к долгосрочному сотрудничеству.\n\n{name} {surname}"),
    # --- спам -------------------------------------------------------------------
    Template("спам", "низкая", "email", "Вы выбраны для участия в акции!!!",
             "Дорогой друг! Только сегодня эксклюзивное предложение: гарантированный доход от 150 000 рублей в месяц без вложений. Перейдите по ссылке http://example.invalid/prize и заберите приз!"),
    Template("спам", "низкая", "email", "Продвижение сайта автосервиса",
             "Здравствуйте! Выведем ваш сайт в ТОП-3 за 2 недели, SEO-продвижение и 10 000 подписчиков в соцсетях. Ответьте «ДА» или отпишитесь по ссылке."),
    Template("спам", "низкая", "chat", None,
             "Кредит без справок и поручителей! Одобрение за 5 минут. Пишите в личные сообщения."),
    Template("спам", "низкая", "form", "ИНВЕСТИЦИИ",
             "Имя: Советник\nТелефон: -\nСообщение: Инвестиции в криптовалюту с доходностью 300% годовых. Биткоин снова растёт! Успейте вложиться."),
    Template("спам", "низкая", "chat", None,
             "asdkjh qwe 123 ???"),
    Template("спам", "низкая", "email", "Срочно подтвердите данные",
             "Уважаемый клиент банка! Ваша карта заблокирована. Срочно подтвердите данные по ссылке https://example.invalid/verify, иначе средства будут списаны."),
]

# Доли категорий в выборке.
CATEGORY_WEIGHTS = {"запись": 0.30, "цена": 0.25, "жалоба": 0.15, "партнёрство": 0.15, "спам": 0.15}


def _phone(rng: random.Random) -> str:
    tail = rng.randint(10, 99)
    forms = [
        f"+7 913 000-00-{tail}",
        f"8 913 000 00 {tail}",
        f"+7 (913) 000-00-{tail}",
        f"89130000{tail}",
        f"+7-913-000-00-{tail}",
    ]
    return rng.choice(forms)


def _surname(rng: random.Random, name: str) -> str:
    """Фамилия, согласованная с полом имени («Ким» не склоняется)."""
    surname = rng.choice(SURNAMES)
    if name in FEMALE_NAMES and surname != "Ким":
        surname += "а"
    return surname


def _budget(rng: random.Random) -> tuple[str, int]:
    value = rng.choice(BUDGETS)
    form = rng.choice(BUDGET_FORMS)
    text = form.format(n=f"{value:,}".replace(",", " "), k=value // 1000)
    return text, value


def generate(n: int = 80, seed: int = 42, start: datetime | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Сгенерировать ``n`` заявок и их разметку. Возвращает (records, labels)."""
    rng = random.Random(seed)
    start = start or datetime(2026, 10, 5, 9, 0)
    by_category: dict[str, list[Template]] = {}
    for template in TEMPLATES:
        by_category.setdefault(template.category, []).append(template)

    categories = list(CATEGORY_WEIGHTS)
    weights = [CATEGORY_WEIGHTS[c] for c in categories]
    records: list[dict[str, Any]] = []
    labels: list[dict[str, Any]] = []
    for i in range(1, n + 1):
        category = rng.choices(categories, weights=weights)[0]
        template = rng.choice(by_category[category])
        name = rng.choice(NAMES)
        female = name in FEMALE_NAMES
        surname = _surname(rng, name)
        phone_raw = _phone(rng)
        service, service_acc = rng.choice(SERVICES)
        date = rng.choice(DATES)
        budget_text, budget_value = _budget(rng)
        values = {
            "name": name,
            "surname": surname,
            "phone": phone_raw,
            "car": rng.choice(CARS),
            "service": service,
            "service_acc": service_acc,
            "date": date,
            "date_past": rng.choice(PAST_DATES),
            "budget": budget_text,
            "budget_plain": f"{budget_value:,}".replace(",", " "),
            "company": rng.choice(COMPANIES),
            **{key: forms[1 if female else 0] for key, forms in VERBS.items()},
        }
        text = template.text.format(**values)
        subject = template.subject.format(**values) if template.subject else None
        received = start + timedelta(hours=rng.randint(0, 24 * 9), minutes=rng.randint(0, 59))
        record_id = f"L-{i:04d}"
        records.append(
            {
                "id": record_id,
                "source": template.source,
                "received_at": received.isoformat(timespec="minutes"),
                **({"subject": subject} if subject else {}),
                "text": text,
            }
        )
        whole = template.text + (template.subject or "")

        def has(key: str) -> bool:
            return "{" + key + "}" in whole

        has_service = has("service") or has("service_acc")
        full_name = f"{name} {surname}" if "{name} {surname}" in template.text else name
        urgency = template.urgency
        if category in ("запись", "цена") and has("date") and "сегодня" in date:
            urgency = "высокая"  # просьба приехать сегодня — срочно по правилам промпта
        labels.append(
            {
                "id": record_id,
                "category": template.category,
                "urgency": urgency,
                "name": full_name if has("name") and category != "спам" else None,
                "phone": normalize_phone(phone_raw) if has("phone") else None,
                "service": service if has_service and category not in ("спам", "партнёрство") else None,
                "desired_date": date if has("date") and category in ("запись", "цена") else None,
                "budget": budget_value if has("budget") and category in ("запись", "цена") else None,
            }
        )
    return records, labels
