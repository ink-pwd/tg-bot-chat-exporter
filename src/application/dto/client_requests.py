"""Результаты анализа обращений: запросы клиентов, их типы и темы."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ClientQuestion:
    """Запрос клиента вместе с его уточнениями."""

    text: str  # сам запрос — так он показывается в отчёте
    client_id: tuple[int, int]  # (chat_id, sender_id): один клиент в одном чате
    clarifications: int = 0  # сколько раз клиент уточнял этот запрос
    clarification_text: str = ""  # тексты уточнений: помогают понять тему запроса
    answer: str = ""  # первый ответ поддержки по существу; пусто — ответа не было


@dataclass(frozen=True)
class QuestionCluster:
    """Группа запросов об одном и том же."""

    label: str  # короткая метка из ключевых понятий: «изменить · оплата · способ»
    representative_question: str  # самая типичная реальная формулировка
    count: int  # сколько разных клиентов спрашивали — по этому темы ранжируются
    requests: int  # сколько всего обращений в теме


@dataclass(frozen=True)
class RequestTopic:
    """К чему относится запрос клиента по классификации поддержки.

    Тип (intent) известен не всегда: иногда понятна только категория.
    """

    category: str  # ключ категории: menu, orders, …
    category_title: str
    intent: str | None  # ключ типа: menu_stop_list, …
    intent_title: str | None
    answer: str | None  # стандартный ответ поддержки на такой запрос
