"""Данные HTML-отчёта за день: ключевые цифры, категории и типы запросов, время ответа, таблица по беседам."""
from dataclasses import dataclass
from datetime import datetime, timedelta

from application.dto.client_requests import QuestionCluster
from domain.value_objects.day_range import DayRange


@dataclass(frozen=True)
class ResponseStats:
    """Время первого ответа поддержки на вопросы клиентов за день."""

    unanswered: int  # клиент ждёт ответа на конец дня
    median: timedelta | None
    average: timedelta | None
    p90: timedelta | None  # 10% самых долгих ожиданий дольше этого
    # вопросы, заданные в рабочее время (Пн–Пт 09:00–20:00) и вне его
    median_work: timedelta | None
    p90_work: timedelta | None
    median_off: timedelta | None
    within_15_work: float | None  # доля вопросов в рабочее время с ответом за 15 минут
    buckets: list[tuple[str, int]]  # («до 5 мин», 12), …


@dataclass(frozen=True)
class HourActivity:
    hour: int  # 0–23, по часовому поясу отчёта
    client_messages: int
    support_messages: int
    asked: int  # вопросов клиентов, ожидание которых началось в этот час
    answered_in_15: int  # из них с ответом за 15 минут


@dataclass(frozen=True)
class LongWait:
    chat_title: str
    asked_at: datetime
    waited: timedelta
    answered: bool


@dataclass(frozen=True)
class CategoryStat:
    key: str
    title: str
    requests: int
    clients: int


@dataclass(frozen=True)
class DialogExample:
    question: str  # как спросил клиент
    answer: str  # что реально ответила поддержка; пусто — ответа не было


@dataclass(frozen=True)
class IntentStat:
    """Тип запроса по классификации поддержки и как часто его задавали."""

    key: str
    title: str
    category_title: str
    requests: int
    clients: int
    clarifications: int
    standard_answer: str  # типовой ответ из базы знаний поддержки, не из переписки
    examples: list[DialogExample]  # реальные вопросы клиентов и ответы поддержки


@dataclass(frozen=True)
class ChatStat:
    title: str
    client_messages: int
    requests: int
    answered: int
    unanswered: int
    median: timedelta | None


@dataclass(frozen=True)
class DailyQuestionReport:
    day: DayRange
    generated_at: datetime
    client_messages: int
    support_messages: int
    conversations: int  # чаты, где клиенты писали за день
    requests: int  # обращения: новые запросы клиентов
    clarifications: int  # уточнения к уже заданным запросам
    reminders: int  # «вы тут?», «есть новости?»
    off_hours_share: float  # доля сообщений клиентов вне рабочего времени
    response: ResponseStats
    categories: list[CategoryStat]  # по убыванию обращений
    intents: list[IntentStat]  # по убыванию обращений
    classified: int  # обращений, у которых определена хотя бы категория
    other_topics: list[QuestionCluster]  # нераспознанные обращения, сгруппированные по смыслу
    hourly: list[HourActivity]
    chats: list[ChatStat]  # по убыванию обращений
    longest_waits: list[LongWait]
