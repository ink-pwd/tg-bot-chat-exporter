"""Аналитика поддержки за день по уже загруженным перепискам.

Определения:
- поддержка — исходящие сообщения аккаунта; клиенты — все остальные участники чата;
- реплика — подряд идущие сообщения одного клиента с паузой не больше 2 минут;
- обращение — содержательное сообщение клиента; новое начинается после паузы больше 3 часов;
- время ответа — от первого неотвеченного содержательного сообщения клиента до первого
  содержательного ответа поддержки. Приветствия клиента отсчёт не запускают,
  приветствия и «секунду, уточню» поддержки его не останавливают.
"""
import logging
import statistics
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from application.dto.report import DailyQuestionReport, HourActivity, LongWait, ResponseStats
from application.interfaces.question_analysis import MessageClassifier, QuestionClusterer
from domain.entities.conversation import Conversation
from domain.entities.daily_conversation_export import DailyConversationExport
from domain.entities.question_cluster import ClientQuestion
from domain.entities.support_message import SupportMessage
from domain.enums.chat_type import ChatType

logger = logging.getLogger(__name__)

TURN_GAP = timedelta(minutes=2)
REQUEST_GAP = timedelta(hours=3)
TOP_CLUSTERS = 10
LONGEST_WAITS = 5
RESPONSE_BUCKETS = [
    ("до 5 мин", timedelta(minutes=5)),
    ("5–15 мин", timedelta(minutes=15)),
    ("15–60 мин", timedelta(hours=1)),
    ("1–3 ч", timedelta(hours=3)),
    ("больше 3 ч", timedelta.max),
]
# чаты, где есть живые клиенты; боты и каналы не анализируются
_ANALYZED_CHATS = {ChatType.PRIVATE, ChatType.GROUP, ChatType.SUPERGROUP}
_TRIVIAL_MEDIA = {"sticker", "gif"}


@dataclass
class _Turn:
    sender_id: int | None
    started_at: datetime
    last_at: datetime
    texts: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(self.texts)


@dataclass
class _ChatStats:
    requests: int = 0
    questions: list[ClientQuestion] = field(default_factory=list)
    responses: list[timedelta] = field(default_factory=list)
    waits: list[LongWait] = field(default_factory=list)
    unanswered: int = 0


def utc_now() -> datetime:
    return datetime.now(UTC)


class AnalyzeDailyQuestions:
    """Синхронный: только вычисления. Вызывать в отдельном потоке, чтобы не блокировать бота."""

    def __init__(
        self,
        classifier: MessageClassifier,
        clusterer: QuestionClusterer,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._classifier = classifier
        self._clusterer = clusterer
        self._clock = clock

    def analyze(self, export: DailyConversationExport) -> DailyQuestionReport:
        timezone = export.day.timezone
        hourly = {hour: [0, 0] for hour in range(24)}
        client_messages = support_messages = conversations = 0
        totals = _ChatStats()
        # до какого момента клиент «ждёт» без ответа: конец дня или сейчас, если день идёт
        cutoff = min(export.day.end, self._clock())

        for conversation in export.conversations:
            if conversation.chat_type not in _ANALYZED_CHATS:
                continue
            messages = [m for m in conversation.messages if m.action is None]
            client = [m for m in messages if not m.is_outgoing]
            if not client:
                continue
            conversations += 1
            client_messages += len(client)
            support_messages += len(messages) - len(client)
            for message in messages:
                hourly[message.sent_at.astimezone(timezone).hour][message.is_outgoing] += 1

            stats = self._analyze_chat(conversation, messages, cutoff)
            totals.requests += stats.requests
            totals.questions += stats.questions
            totals.responses += stats.responses
            totals.waits += stats.waits
            totals.unanswered += stats.unanswered

        clusters = self._clusterer.cluster(totals.questions)[:TOP_CLUSTERS]
        report = DailyQuestionReport(
            account_name=export.profile.display_name,
            day=export.day,
            generated_at=self._clock(),
            client_messages=client_messages,
            support_messages=support_messages,
            conversations=conversations,
            requests=totals.requests,
            questions=len(totals.questions),
            response=_response_stats(totals.responses, totals.unanswered),
            clusters=clusters,
            hourly=[HourActivity(h, counts[0], counts[1]) for h, counts in hourly.items()],
            longest_waits=sorted(totals.waits, key=lambda w: -w.waited)[:LONGEST_WAITS],
        )
        logger.info(
            "Question analysis completed: requests=%s questions=%s clusters=%s",
            report.requests,
            report.questions,
            len(clusters),
        )
        return report

    def _analyze_chat(
        self, conversation: Conversation, messages: list[SupportMessage], cutoff: datetime
    ) -> _ChatStats:
        stats = _ChatStats()
        last_substantive: dict[int | None, datetime] = {}
        turns: list[_Turn] = []
        waiting_since: datetime | None = None

        for message in messages:
            if message.is_outgoing:
                if waiting_since is not None and self._is_real_answer(message):
                    waited = message.sent_at - waiting_since
                    stats.responses.append(waited)
                    stats.waits.append(LongWait(conversation.title, waiting_since, waited, True))
                    waiting_since = None
                continue

            if not self._is_substantive(message):
                continue
            previous = last_substantive.get(message.sender_id)
            if previous is None or message.sent_at - previous > REQUEST_GAP:
                stats.requests += 1
            last_substantive[message.sender_id] = message.sent_at
            if waiting_since is None:
                waiting_since = message.sent_at

            turn = turns[-1] if turns else None
            if (
                turn is None
                or turn.sender_id != message.sender_id
                or message.sent_at - turn.last_at > TURN_GAP
            ):
                turn = _Turn(message.sender_id, message.sent_at, message.sent_at)
                turns.append(turn)
            turn.last_at = message.sent_at
            if message.text.strip():
                turn.texts.append(message.text.strip())

        if waiting_since is not None:
            stats.unanswered += 1
            waited = max(cutoff - waiting_since, timedelta(0))
            stats.waits.append(LongWait(conversation.title, waiting_since, waited, False))

        stats.questions = [
            ClientQuestion(turn.text, (conversation.chat_id, turn.sender_id or 0))
            for turn in turns
            if turn.texts and self._classifier.is_question(turn.text)
        ]
        return stats

    def _is_substantive(self, message: SupportMessage) -> bool:
        if message.media_type in _TRIVIAL_MEDIA:
            return False
        if not message.text.strip():
            return message.media_type is not None  # скриншот без подписи — тоже обращение
        return not self._classifier.is_trivial(message.text)

    def _is_real_answer(self, message: SupportMessage) -> bool:
        if not message.text.strip():
            return message.media_type is not None and message.media_type not in _TRIVIAL_MEDIA
        return not (
            self._classifier.is_trivial(message.text) or self._classifier.is_holding_reply(message.text)
        )


def _response_stats(responses: list[timedelta], unanswered: int) -> ResponseStats:
    buckets = []
    lower = timedelta(0)
    for label, upper in RESPONSE_BUCKETS:
        buckets.append((label, sum(1 for r in responses if lower <= r < upper)))
        lower = upper
    if not responses:
        return ResponseStats(0, unanswered, None, None, buckets)
    seconds = [r.total_seconds() for r in responses]
    return ResponseStats(
        answered=len(responses),
        unanswered=unanswered,
        median=timedelta(seconds=statistics.median(seconds)),
        average=timedelta(seconds=statistics.fmean(seconds)),
        buckets=buckets,
    )
