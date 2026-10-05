from typing import Protocol

from domain.entities.question_cluster import ClientQuestion, QuestionCluster


class MessageClassifier(Protocol):
    """Простые эвристики о смысле одного сообщения (ru/uk)."""

    def is_trivial(self, text: str) -> bool:
        """Приветствие, благодарность, «ок», «+» — не обращение и не ответ."""
        ...

    def is_holding_reply(self, text: str) -> bool:
        """«Секунду, уточню» — поддержка ещё не ответила по существу."""
        ...

    def is_question(self, text: str) -> bool: ...


class QuestionClusterer(Protocol):
    def cluster(self, questions: list[ClientQuestion]) -> list[QuestionCluster]:
        """Группы вопросов по смыслу, по убыванию числа клиентов."""
        ...
