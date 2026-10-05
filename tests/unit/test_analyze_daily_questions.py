from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from application.use_cases.analyze_daily_questions import AnalyzeDailyQuestions
from domain.entities.conversation import Conversation
from domain.entities.daily_conversation_export import DailyConversationExport
from domain.entities.question_cluster import ClientQuestion, QuestionCluster
from domain.entities.support_message import SupportMessage
from domain.enums.chat_type import ChatType
from domain.value_objects.day_range import DayRange
from domain.value_objects.telegram_profile import TelegramProfile

KYIV = ZoneInfo("Europe/Kyiv")
DAY = DayRange(date(2026, 10, 4), KYIV)
SUPPORT = 999
NEXT_DAY = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)  # день закончился


class FakeClassifier:
    trivial = {"привет", "спасибо", "добрый день", "ок", "дякую", ""}

    def is_trivial(self, text):
        return text.lower().strip(" !") in self.trivial

    def is_holding_reply(self, text):
        return "уточню" in text.lower()

    def is_question(self, text):
        return "?" in text


class RecordingClusterer:
    def __init__(self):
        self.questions: list[ClientQuestion] = []

    def cluster(self, questions):
        self.questions = questions
        by_text = {}
        for q in questions:
            by_text.setdefault(q.text, set()).add(q.client_id)
        return [
            QuestionCluster(text, text, len(clients), [])
            for text, clients in sorted(by_text.items(), key=lambda kv: -len(kv[1]))
        ]


def at(hour: int, minute: int = 0, second: int = 0) -> datetime:
    """Время 4 октября по Киеву."""
    return datetime(2026, 10, 4, hour, minute, second, tzinfo=KYIV).astimezone(UTC)


_ids = iter(range(1, 10_000))


def client(sent_at: datetime, text: str, sender: int = 1, media: str | None = None) -> SupportMessage:
    return SupportMessage(next(_ids), 0, sender, "Клиент", text, sent_at, None, False, None, None, media, None)


def support(sent_at: datetime, text: str) -> SupportMessage:
    return SupportMessage(next(_ids), 0, SUPPORT, "Поддержка", text, sent_at, None, True, None, None, None, None)


def chat(*messages, chat_id: int = 10, kind: ChatType = ChatType.PRIVATE, title: str = "Клиент") -> Conversation:
    return Conversation(chat_id, title, kind, list(messages))


def analyze(*conversations, now: datetime = NEXT_DAY, clusterer=None):
    export = DailyConversationExport(1, TelegramProfile(555, "Support", None), None, DAY, now, list(conversations))
    clusterer = clusterer or RecordingClusterer()
    return AnalyzeDailyQuestions(FakeClassifier(), clusterer, lambda: now).analyze(export)


# --- время ответа ---------------------------------------------------------------


def test_response_time_from_question_to_answer():
    report = analyze(chat(client(at(10), "Где заказ?"), support(at(10, 4), "Уже в пути")))

    assert report.response.answered == 1
    assert report.response.median == timedelta(minutes=4)
    assert report.response.average == timedelta(minutes=4)


def test_client_greeting_does_not_start_timer():
    report = analyze(
        chat(
            client(at(9), "Привет"),
            client(at(10), "Где заказ?"),
            support(at(10, 2), "Уже в пути"),
        )
    )

    assert report.response.median == timedelta(minutes=2)


def test_support_greeting_and_holding_are_not_answers():
    report = analyze(
        chat(
            client(at(10), "Где заказ?"),
            support(at(10, 1), "Добрый день!"),
            support(at(10, 2), "Секунду, уточню"),
            support(at(10, 15), "Заказ передан курьеру"),
        )
    )

    assert report.response.median == timedelta(minutes=15)


def test_follow_up_messages_wait_for_first_unanswered():
    report = analyze(
        chat(
            client(at(10), "Где заказ?"),
            client(at(10, 5), "Алло?"),
            support(at(10, 20), "Уже в пути"),
        )
    )

    assert report.response.answered == 1
    assert report.response.median == timedelta(minutes=20)


def test_unanswered_until_end_of_day():
    report = analyze(chat(client(at(22), "Где заказ?")))

    assert report.response.answered == 0
    assert report.response.unanswered == 1
    assert report.response.median is None
    assert report.longest_waits[0].waited == timedelta(hours=2)
    assert not report.longest_waits[0].answered


def test_unanswered_today_counts_until_now():
    now = at(15)
    report = analyze(chat(client(at(14, 30), "Где заказ?")), now=now)

    assert report.longest_waits[0].waited == timedelta(minutes=30)


def test_median_and_average_across_chats():
    report = analyze(
        chat(client(at(10), "А?"), support(at(10, 2), "Ответ"), chat_id=1),
        chat(client(at(11), "Б?"), support(at(11, 4), "Ответ"), chat_id=2),
        chat(client(at(12), "В?"), support(at(14), "Ответ"), chat_id=3),
    )

    assert report.response.median == timedelta(minutes=4)
    assert report.response.average == timedelta(minutes=42)
    assert dict(report.response.buckets) == {
        "до 5 мин": 2, "5–15 мин": 0, "15–60 мин": 0, "1–3 ч": 1, "больше 3 ч": 0,
    }


def test_support_message_without_question_is_ignored():
    report = analyze(chat(support(at(9), "Напоминаем о записи"), client(at(10), "Спасибо")))

    assert report.response.answered == 0
    assert report.response.unanswered == 0


# --- обращения ------------------------------------------------------------------


def test_requests_split_by_three_hour_pause():
    report = analyze(
        chat(
            client(at(9), "Где заказ?"),
            client(at(9, 30), "Есть новости?"),
            support(at(10), "В пути"),
            client(at(14), "Заказ пришёл не тот"),  # пауза 4.5 часа — новое обращение
        )
    )

    assert report.requests == 2


def test_greetings_and_thanks_are_not_requests():
    report = analyze(chat(client(at(9), "Привет"), client(at(18), "Спасибо!")))

    assert report.requests == 0


def test_screenshot_without_text_is_a_request():
    report = analyze(chat(client(at(9), "", media="photo")))

    assert report.requests == 1


def test_sticker_is_not_a_request():
    report = analyze(chat(client(at(9), "", media="sticker")))

    assert report.requests == 0


def test_group_chat_counts_each_client():
    report = analyze(
        chat(
            client(at(9), "Где заказ?", sender=1),
            client(at(9, 1), "И мой где?", sender=2),
            support(at(9, 10), "Оба в пути"),
            kind=ChatType.GROUP,
        )
    )

    assert report.requests == 2
    assert report.conversations == 1


def test_bots_and_channels_are_not_analyzed():
    report = analyze(
        chat(client(at(9), "Где заказ?"), kind=ChatType.BOT, chat_id=1),
        chat(client(at(9), "Новость дня?"), kind=ChatType.CHANNEL, chat_id=2),
    )

    assert report.conversations == 0
    assert report.requests == 0


def test_service_messages_are_ignored():
    service = SupportMessage(1, 0, 1, None, "", at(9), None, False, None, None, None, "MessageActionChatAddUser")

    report = analyze(chat(service))

    assert report.conversations == 0


# --- вопросы и темы -------------------------------------------------------------


def test_consecutive_messages_form_one_question():
    clusterer = RecordingClusterer()

    analyze(
        chat(
            client(at(10, 0, 0), "Добрый день"),
            client(at(10, 0, 20), "подскажите"),
            client(at(10, 0, 40), "как поменять карту?"),
        ),
        clusterer=clusterer,
    )

    assert [q.text for q in clusterer.questions] == ["подскажите как поменять карту?"]


def test_messages_after_long_pause_are_separate_questions():
    clusterer = RecordingClusterer()

    analyze(chat(client(at(10), "Где заказ?"), client(at(10, 30), "Можно поменять адрес?")), clusterer=clusterer)

    assert len(clusterer.questions) == 2


def test_questions_are_tagged_by_client():
    clusterer = RecordingClusterer()

    analyze(
        chat(client(at(9), "Где заказ?", sender=1), client(at(9, 1), "Где заказ?", sender=2), kind=ChatType.GROUP),
        clusterer=clusterer,
    )

    assert {q.client_id for q in clusterer.questions} == {(10, 1), (10, 2)}


def test_report_counts_and_top_clusters():
    report = analyze(
        chat(client(at(9), "Где заказ?"), support(at(9, 5), "В пути"), chat_id=1),
        chat(client(at(10), "Где заказ?"), chat_id=2),
        chat(client(at(11), "Как вернуть деньги?"), chat_id=3),
    )

    assert report.questions == 3
    assert report.client_messages == 3
    assert report.support_messages == 1
    assert [(c.label, c.count) for c in report.clusters] == [("Где заказ?", 2), ("Как вернуть деньги?", 1)]


def test_hourly_activity_in_report_timezone():
    report = analyze(chat(client(at(9, 30), "Где заказ?"), support(at(9, 40), "В пути")))

    nine = report.hourly[9]
    assert (nine.client_messages, nine.support_messages) == (1, 1)
    assert sum(h.client_messages for h in report.hourly) == 1
