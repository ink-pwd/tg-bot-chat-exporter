from dataclasses import dataclass
from datetime import datetime, timedelta

from domain.entities.question_cluster import QuestionCluster
from domain.value_objects.day_range import DayRange


@dataclass(frozen=True)
class ResponseStats:
    """Время ответа поддержки на вопросы клиентов за день."""

    answered: int
    unanswered: int  # клиент ждёт ответа на конец дня
    median: timedelta | None
    average: timedelta | None
    buckets: list[tuple[str, int]]  # («до 5 мин», 12), …


@dataclass(frozen=True)
class HourActivity:
    hour: int  # 0–23, по часовому поясу отчёта
    client_messages: int
    support_messages: int


@dataclass(frozen=True)
class LongWait:
    chat_title: str
    asked_at: datetime
    waited: timedelta
    answered: bool


@dataclass(frozen=True)
class DailyQuestionReport:
    account_name: str
    day: DayRange
    generated_at: datetime
    client_messages: int
    support_messages: int
    conversations: int  # чаты, где клиенты писали за день
    requests: int  # обращения: новое — после паузы клиента больше 3 часов
    questions: int
    response: ResponseStats
    clusters: list[QuestionCluster]  # по убыванию числа клиентов
    hourly: list[HourActivity]
    longest_waits: list[LongWait]
