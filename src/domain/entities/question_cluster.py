from dataclasses import dataclass


@dataclass(frozen=True)
class ClientQuestion:
    text: str
    client_id: tuple[int, int]  # (chat_id, sender_id): один клиент в одном чате


@dataclass(frozen=True)
class QuestionCluster:
    """Группа запросов об одном и том же."""

    label: str  # короткая метка из ключевых понятий: «изменить · оплата · способ»
    representative_question: str  # самая типичная реальная формулировка
    count: int  # сколько разных клиентов спрашивали
    examples: list[str]
