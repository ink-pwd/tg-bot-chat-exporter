"""Аналитика поддержки за день по уже загруженным перепискам.

Определения:
- поддержка — админы беседы и её владелец; клиенты — все остальные участники;
- реплика — подряд идущие сообщения одного клиента с паузой не больше 2 минут;
  любое сообщение поддержки между ними начинает новую реплику;
- обращение — новый запрос клиента: реплика с вопросом или просьбой либо скриншот/файл
  без подписи. В анализ тем идёт только сам запрос, без приветствия и вступления;
- уточнение — реплика, которая продолжает предыдущий запрос того же клиента
  (см. _linked_request); засчитывается к нему, а не новым обращением;
- напоминание — «вы тут?», «есть новости?»: не запрос и не уточнение;
- тип и категория обращения — по классификации поддержки Dots (RequestClassifier);
  нераспознанные обращения группируются по смыслу в «прочие темы»;
- время ответа — от первого неотвеченного содержательного сообщения клиента до первого
  содержательного ответа поддержки. Приветствия клиента отсчёт не запускают,
  приветствия и «секунду, уточню» поддержки его не останавливают;
- рабочее время — Пн–Пт 09:00–20:00 по часовому поясу отчёта.
"""
import logging
import statistics
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from application.dto.client_requests import ClientQuestion
from application.dto.daily_report import (
    CategoryStat,
    ChatStat,
    DailyQuestionReport,
    DialogExample,
    HourActivity,
    IntentStat,
    LongWait,
    ResponseStats,
)
from application.ports.text_analysis import (
    MessageClassifier,
    QuestionClusterer,
    RequestClassifier,
    TopicTokenizer,
)
from application.services.personal_data_masking import mask_personal_data
from domain.entities.conversation import Conversation
from domain.entities.daily_conversation_export import DailyConversationExport
from domain.entities.support_message import SupportMessage
from domain.enums.chat_type import ChatType

logger = logging.getLogger(__name__)

TURN_GAP = timedelta(minutes=2)
# реплика позже этого после последнего сообщения запроса уточнением не считается
# (кроме ответа на сообщение из этого запроса через reply)
CLARIFICATION_WINDOW = timedelta(hours=2)
# доля общих понятий, при которой реплика — та же тема (от меньшего из двух наборов)
SAME_TOPIC_OVERLAP = 0.5
WORK_DAYS = range(0, 5)  # Пн–Пт
WORK_HOURS = range(9, 20)  # 09:00–19:59
FAST_REPLY = timedelta(minutes=15)
# нераспознанных обращений за день немного — показываем почти все
TOP_OTHER_TOPICS = 30
INTENT_EXAMPLES = 3
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
    reply_to_ids: list[int] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(self.texts)


@dataclass
class _Request:
    sender_id: int | None
    last_at: datetime
    texts: list[str] = field(default_factory=list)  # запрос и тексты уточнений
    tokens: set[str] = field(default_factory=set)
    clarifications: int = 0
    answer: str = ""  # первый ответ поддержки по существу


@dataclass(frozen=True)
class _Response:
    asked_at: datetime
    waited: timedelta


@dataclass
class _ChatStats:
    requests: int = 0
    clarifications: int = 0
    reminders: int = 0
    questions: list[ClientQuestion] = field(default_factory=list)
    responses: list[_Response] = field(default_factory=list)
    waits: list[LongWait] = field(default_factory=list)
    unanswered: int = 0
    unanswered_since: list[datetime] = field(default_factory=list)


@dataclass
class _IntentTotals:
    requests: int = 0
    clarifications: int = 0
    clients: set[tuple[int, int]] = field(default_factory=set)
    examples: list[DialogExample] = field(default_factory=list)


def utc_now() -> datetime:
    return datetime.now(UTC)


def is_working_time(moment: datetime, timezone: ZoneInfo) -> bool:
    local = moment.astimezone(timezone)
    return local.weekday() in WORK_DAYS and local.hour in WORK_HOURS


class AnalyzeDailyQuestions:
    """Синхронный: только вычисления. Вызывать в отдельном потоке, чтобы не блокировать бота."""

    def __init__(
        self,
        classifier: MessageClassifier,
        topics: TopicTokenizer,
        request_classifier: RequestClassifier,
        clusterer: QuestionClusterer,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._classifier = classifier
        self._topics = topics
        self._request_classifier = request_classifier
        self._clusterer = clusterer
        self._clock = clock

    def analyze(self, export: DailyConversationExport) -> DailyQuestionReport:
        timezone = export.day.timezone
        hourly = {hour: [0, 0, 0, 0] for hour in range(24)}  # клиент, поддержка, вопросов, за 15 мин
        client_messages = support_messages = conversations = off_hours = 0
        totals = _ChatStats()
        chats: list[ChatStat] = []
        # до какого момента клиент «ждёт» без ответа: конец дня или сейчас, если день идёт
        cutoff = min(export.day.end, self._clock())

        for conversation in export.conversations:
            if conversation.chat_type not in _ANALYZED_CHATS:
                continue
            messages = [m for m in conversation.messages if m.action is None]
            client = [m for m in messages if not m.from_support]
            if not client:
                continue
            conversations += 1
            client_messages += len(client)
            support_messages += len(messages) - len(client)
            off_hours += sum(1 for m in client if not is_working_time(m.sent_at, timezone))
            for message in messages:
                hourly[message.sent_at.astimezone(timezone).hour][int(message.from_support)] += 1

            stats = self._analyze_chat(conversation, messages, cutoff)
            for response in stats.responses:
                counts = hourly[response.asked_at.astimezone(timezone).hour]
                counts[2] += 1
                counts[3] += response.waited <= FAST_REPLY
            for asked_at in stats.unanswered_since:
                hourly[asked_at.astimezone(timezone).hour][2] += 1
            chats.append(
                ChatStat(
                    title=conversation.title,
                    client_messages=len(client),
                    requests=stats.requests,
                    answered=len(stats.responses),
                    unanswered=stats.unanswered,
                    median=_median([r.waited for r in stats.responses]),
                )
            )
            totals.requests += stats.requests
            totals.clarifications += stats.clarifications
            totals.reminders += stats.reminders
            totals.questions += stats.questions
            totals.responses += stats.responses
            totals.waits += stats.waits
            totals.unanswered += stats.unanswered

        categories, intents, unclassified = self._classify(totals.questions)
        other_topics = self._clusterer.cluster(unclassified)[:TOP_OTHER_TOPICS]
        report = DailyQuestionReport(
            day=export.day,
            generated_at=self._clock(),
            client_messages=client_messages,
            support_messages=support_messages,
            conversations=conversations,
            requests=totals.requests,
            clarifications=totals.clarifications,
            reminders=totals.reminders,
            off_hours_share=off_hours / client_messages if client_messages else 0.0,
            response=_response_stats(totals.responses, totals.unanswered, timezone),
            categories=categories,
            intents=intents,
            classified=sum(c.requests for c in categories),
            other_topics=other_topics,
            hourly=[HourActivity(h, *counts) for h, counts in hourly.items()],
            chats=sorted(chats, key=lambda c: (-c.requests, -c.client_messages, c.title)),
            longest_waits=sorted(totals.waits, key=lambda w: -w.waited)[:LONGEST_WAITS],
        )
        logger.info(
            "Question analysis completed: requests=%s classified=%s intents=%s other_topics=%s",
            report.requests,
            report.classified,
            len(intents),
            len(other_topics),
        )
        return report

    def _classify(
        self, questions: list[ClientQuestion]
    ) -> tuple[list[CategoryStat], list[IntentStat], list[ClientQuestion]]:
        """Тип и категория каждого запроса; нераспознанные — для группировки по смыслу."""
        categories: dict[str, list] = {}  # ключ → [название, обращений, клиенты]
        intents: dict[str, tuple[object, _IntentTotals]] = {}
        unclassified: list[ClientQuestion] = []

        for question in questions:
            topic = self._request_classifier.classify(
                f"{question.text} {question.clarification_text}".strip()
            )
            if topic is None:
                unclassified.append(question)
                continue
            category = categories.setdefault(topic.category, [topic.category_title, 0, set()])
            category[1] += 1
            category[2].add(question.client_id)
            if topic.intent is None:
                continue
            _, intent = intents.setdefault(topic.intent, (topic, _IntentTotals()))
            intent.requests += 1
            intent.clarifications += question.clarifications
            intent.clients.add(question.client_id)
            if len(intent.examples) < INTENT_EXAMPLES and all(
                e.question != question.text for e in intent.examples
            ):
                intent.examples.append(DialogExample(question.text, question.answer))

        category_stats = sorted(
            (CategoryStat(key, title, requests, len(clients)) for key, (title, requests, clients) in categories.items()),
            key=lambda c: (-c.requests, -c.clients, c.title),
        )
        intent_stats = sorted(
            (
                IntentStat(
                    key=key,
                    title=topic.intent_title,
                    category_title=topic.category_title,
                    requests=totals.requests,
                    clients=len(totals.clients),
                    clarifications=totals.clarifications,
                    standard_answer=topic.answer,
                    examples=totals.examples,
                )
                for key, (topic, totals) in intents.items()
            ),
            key=lambda i: (-i.requests, -i.clients, i.title),
        )
        return category_stats, intent_stats, unclassified

    def _analyze_chat(
        self, conversation: Conversation, messages: list[SupportMessage], cutoff: datetime
    ) -> _ChatStats:
        stats = _ChatStats()
        turns: list[_Turn] = []
        turn: _Turn | None = None  # реплика клиента, которую ещё можно продолжить
        # сообщение → индекс реплики клиента, к которой оно относится (для reply)
        turn_of_message: dict[int, int] = {}
        # ответы поддержки по существу: (индекс реплики клиента перед ответом, текст)
        replies: list[tuple[int, str]] = []
        waiting_since: datetime | None = None

        for message in messages:
            if message.from_support:
                # поддержка вмешалась: следующее сообщение клиента — уже новая реплика
                turn = None
                if turns:
                    # ответ поддержки относится к последней реплике клиента перед ним
                    turn_of_message[message.id] = len(turns) - 1
                    if message.text.strip() and self._is_real_answer(message):
                        replies.append((len(turns) - 1, message.text.strip()))
                if waiting_since is not None and self._is_real_answer(message):
                    waited = message.sent_at - waiting_since
                    stats.responses.append(_Response(waiting_since, waited))
                    stats.waits.append(LongWait(conversation.title, waiting_since, waited, True))
                    waiting_since = None
                continue

            if not self._is_substantive(message):
                continue
            if waiting_since is None:
                waiting_since = message.sent_at

            if (
                turn is None
                or turn.sender_id != message.sender_id
                or message.sent_at - turn.last_at > TURN_GAP
            ):
                turn = _Turn(message.sender_id, message.sent_at, message.sent_at)
                turns.append(turn)
            turn_of_message[message.id] = len(turns) - 1
            turn.last_at = message.sent_at
            if message.text.strip():
                turn.texts.append(message.text.strip())
            if message.reply_to_id is not None:
                turn.reply_to_ids.append(message.reply_to_id)

        if waiting_since is not None:
            stats.unanswered += 1
            stats.unanswered_since.append(waiting_since)
            waited = max(cutoff - waiting_since, timedelta(0))
            stats.waits.append(LongWait(conversation.title, waiting_since, waited, False))

        requests, request_of_turn = self._group_requests(turns, turn_of_message, stats)
        for turn_index, text in replies:
            request = request_of_turn.get(turn_index)
            if request is not None and not request.answer:
                request.answer = text
        # дальше тексты идут в отчёт — телефоны, пароли и токены прячутся уже здесь
        stats.questions = [
            ClientQuestion(
                mask_personal_data(request.texts[0]),
                (conversation.chat_id, request.sender_id or 0),
                request.clarifications,
                mask_personal_data(" ".join(request.texts[1:])),
                mask_personal_data(request.answer),
            )
            for request in requests
            if request.texts
        ]
        return stats

    def _group_requests(
        self, turns: list[_Turn], turn_of_message: dict[int, int], stats: _ChatStats
    ) -> tuple[list[_Request], dict[int, _Request]]:
        """Делит реплики клиентов на новые запросы, уточнения и напоминания.

        Возвращает запросы и к какому запросу относится каждая реплика (по индексу).
        """
        requests: list[_Request] = []
        request_of_turn: dict[int, _Request] = {}
        last_request: dict[int | None, _Request] = {}

        for index, turn in enumerate(turns):
            text = turn.text
            previous = last_request.get(turn.sender_id)
            if text and self._classifier.is_ping(text):
                stats.reminders += 1
                if previous is not None:
                    request_of_turn[index] = previous
                continue

            part = self._classifier.request_part(text) if text else ""
            tokens = set(self._topics.topic_tokens(part)) if part else set()
            replied = _replied_request(turn, turn_of_message, request_of_turn)
            linked = self._linked_request(turn, text, tokens, previous, replied)

            if linked is not None:
                linked.clarifications += 1
                stats.clarifications += 1
                if part:
                    linked.texts.append(part)
                linked.tokens |= tokens
                linked.last_at = turn.last_at
                request_of_turn[index] = linked
                last_request[turn.sender_id] = linked
                continue

            # новый запрос — только вопрос, просьба или скриншот без подписи
            if text and not self._classifier.is_question(text):
                if previous is not None:
                    request_of_turn[index] = previous
                continue
            request = _Request(turn.sender_id, turn.last_at, [part] if part else [], tokens)
            requests.append(request)
            stats.requests += 1
            request_of_turn[index] = request
            last_request[turn.sender_id] = request
        return requests, request_of_turn

    def _linked_request(
        self,
        turn: _Turn,
        text: str,
        tokens: set[str],
        previous: _Request | None,
        replied: _Request | None,
    ) -> _Request | None:
        """Запрос, который продолжает эта реплика, или None, если это новый запрос.

        По порядку:
        1. reply на сообщение своего запроса (или на ответ поддержки по нему) — уточнение;
        2. «ещё вопрос», «и ещё…» — новый запрос;
        3. больше 2 часов после предыдущего запроса — новый запрос;
        4. скриншот без подписи, «а если…», «не получилось» — уточнение;
        5. своей темы нет («а как это сделать?») — уточнение;
        6. темы пересекаются хотя бы наполовину — уточнение, иначе новый запрос.
        """
        if replied is not None and replied.sender_id == turn.sender_id:
            return replied
        if previous is None:
            return None
        if text and self._classifier.starts_new_topic(text):
            return None
        if turn.started_at - previous.last_at > CLARIFICATION_WINDOW:
            return None
        if not text or self._classifier.is_follow_up(text):
            return previous
        if not tokens:
            return previous
        if not previous.tokens:
            return None
        overlap = len(tokens & previous.tokens) / min(len(tokens), len(previous.tokens))
        return previous if overlap >= SAME_TOPIC_OVERLAP else None

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


def _replied_request(
    turn: _Turn, turn_of_message: dict[int, int], request_of_turn: dict[int, _Request]
) -> _Request | None:
    """Запрос, к которому относится сообщение, на которое клиент ответил через reply."""
    for message_id in turn.reply_to_ids:
        replied_turn = turn_of_message.get(message_id)
        if replied_turn is not None and replied_turn in request_of_turn:
            return request_of_turn[replied_turn]
    return None


def _median(values: list[timedelta]) -> timedelta | None:
    if not values:
        return None
    return timedelta(seconds=statistics.median(v.total_seconds() for v in values))


def _p90(values: list[timedelta]) -> timedelta | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    seconds = statistics.quantiles([v.total_seconds() for v in values], n=10, method="inclusive")
    return timedelta(seconds=seconds[-1])


def _response_stats(responses: list[_Response], unanswered: int, timezone: ZoneInfo) -> ResponseStats:
    waited = [r.waited for r in responses]
    buckets = []
    lower = timedelta(0)
    for label, upper in RESPONSE_BUCKETS:
        buckets.append((label, sum(1 for w in waited if lower <= w < upper)))
        lower = upper
    work = [r.waited for r in responses if is_working_time(r.asked_at, timezone)]
    off = [r.waited for r in responses if not is_working_time(r.asked_at, timezone)]
    return ResponseStats(
        unanswered=unanswered,
        median=_median(waited),
        average=timedelta(seconds=statistics.fmean(w.total_seconds() for w in waited)) if waited else None,
        p90=_p90(waited),
        median_work=_median(work),
        p90_work=_p90(work),
        median_off=_median(off),
        within_15_work=sum(1 for w in work if w <= FAST_REPLY) / len(work) if work else None,
        buckets=buckets,
    )
