from typing import Protocol

from domain.entities.question_cluster import ClientQuestion, QuestionCluster
from domain.value_objects.request_topic import RequestTopic


class MessageClassifier(Protocol):
    """Простые эвристики о смысле одного сообщения (ru/uk)."""

    def is_trivial(self, text: str) -> bool:
        """Приветствие, благодарность, «ок», «+» — не обращение и не ответ."""
        ...

    def is_holding_reply(self, text: str) -> bool:
        """«Секунду, уточню» — поддержка ещё не ответила по существу."""
        ...

    def is_question(self, text: str) -> bool: ...

    def is_ping(self, text: str) -> bool:
        """«Вы тут?», «есть новости?» — напоминание, а не запрос.

        Должен ошибаться только в сторону «не пинг»: потерять реальный запрос хуже.
        """
        ...

    def request_part(self, text: str) -> str:
        """Из реплики только предложения с вопросом или просьбой, без вступления и контекста."""
        ...

    def is_follow_up(self, text: str) -> bool:
        """«А если…», «не получилось», «то есть…» — продолжение предыдущего запроса."""
        ...

    def starts_new_topic(self, text: str) -> bool:
        """«Ещё вопрос», «и ещё…» — клиент явно переходит к новому запросу."""
        ...


class TopicTokenizer(Protocol):
    def topic_tokens(self, text: str) -> frozenset[str]:
        """Понятия и значимые слова запроса — по ним видно, та же это тема или другая."""
        ...


class RequestClassifier(Protocol):
    def classify(self, text: str) -> RequestTopic | None:
        """Тип и категория запроса по классификации поддержки; None — не распознан."""
        ...


class QuestionClusterer(Protocol):
    def cluster(self, questions: list[ClientQuestion]) -> list[QuestionCluster]:
        """Группы запросов по смыслу, по убыванию числа клиентов."""
        ...
