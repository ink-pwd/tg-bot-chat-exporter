"""HTML-отчёт по поддержке за день — в том же стиле, что годовой отчёт по поддержке Dots.

Один самодостаточный файл: стили внутри, графики — встроенный SVG и CSS, без JavaScript
и внешних ресурсов. Открывается офлайн в браузере, светлая и тёмная тема.
Весь текст из переписок экранируется; личные данные маскируются ещё при анализе.
"""
from datetime import timedelta
from html import escape

from application.dto.report import (
    CategoryStat,
    ChatStat,
    DailyQuestionReport,
    HourActivity,
    IntentStat,
    ResponseStats,
)
from domain.entities.question_cluster import QuestionCluster

TOP_INTENTS = 10

_CATEGORY_COLORS = {
    "pos": "--c1", "menu": "--c2", "venue": "--c3", "orders": "--c4", "couriers": "--c5",
    "payments": "--c6", "loyalty": "--c7", "promo": "--c8", "marketing": "--c1", "apps": "--c2",
    "clients": "--c3", "access": "--c4", "billing": "--c5", "requests": "--c6",
}
_BUCKET_COLORS = ["--good", "--c3", "--c4", "--c2", "--bad"]

_STYLE = """
:root{color-scheme:light;
--bg:#f6f5f2;--surface:#fcfcfb;--border:#e4e2dc;--grid:#ecebe6;--text:#0b0b0b;--text-2:#52514e;
--muted:#85837d;--chip:#f0efec;--s1:#2a78d6;--s2:#eb6834;
--c1:#2a78d6;--c2:#eb6834;--c3:#1baf7a;--c4:#eda100;--c5:#e87ba4;--c6:#008300;--c7:#4a3aa7;--c8:#e34948;
--warn:#9a6400;--warn-bg:#fdf3dc;--bad:#c4342f;--good:#1d7a3a}
@media (prefers-color-scheme:dark){:root{color-scheme:dark;
--bg:#121211;--surface:#1a1a19;--border:#2e2e2b;--grid:#262624;--text:#fff;--text-2:#c3c2b7;
--muted:#8f8e86;--chip:#262624;--s1:#3987e5;--s2:#d95926;
--c1:#3987e5;--c2:#d95926;--c3:#199e70;--c4:#c98500;--c5:#d55181;--c6:#008300;--c7:#9085e9;--c8:#e66767;
--warn:#e8b44a;--warn-bg:#3a2e14;--bad:#f07b77;--good:#6fcf8e}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,sans-serif}
.wrap{max-width:1100px;margin:0 auto;padding:28px 16px 64px}
h1{font-size:28px;margin:0 0 4px;letter-spacing:-.02em}
h2{font-size:19px;margin:36px 0 4px}
.sub{color:var(--text-2);margin:0 0 14px}
.note{color:var(--muted);font-size:13px}
.card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:18px;margin-top:12px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(165px,1fr));gap:12px;margin-top:14px}
.kpi .v{font-size:26px;font-weight:650;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.kpi .l{color:var(--text-2);font-size:13px}
.kpi .d{color:var(--muted);font-size:12px;margin-top:2px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media (max-width:860px){.grid2{grid-template-columns:1fr}}
svg{display:block;width:100%;height:auto}
svg text{fill:var(--text-2);font-size:11px;font-family:inherit}
.legend{display:flex;gap:6px 16px;font-size:13px;color:var(--text-2);margin:4px 0 8px;flex-wrap:wrap}
.legend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px;vertical-align:-1px}
table{width:100%;border-collapse:collapse;font-size:14px}
th{text-align:left;font-weight:600;color:var(--text-2);font-size:12px;text-transform:uppercase;
letter-spacing:.04em;border-bottom:1px solid var(--border);padding:8px;white-space:nowrap}
td{border-bottom:1px solid var(--grid);padding:8px;vertical-align:top}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.scroll{overflow-x:auto}
.bar{height:8px;border-radius:0 4px 4px 0;background:var(--s1);min-width:2px}
.chip{display:inline-block;font-size:12px;padding:1px 7px;border-radius:6px;background:var(--chip);
color:var(--text-2);white-space:nowrap;margin:0 4px 4px 0}
.cat{display:inline-flex;align-items:center;gap:6px;font-size:12px;color:var(--text-2);white-space:nowrap}
.cat i{width:9px;height:9px;border-radius:3px;display:inline-block}
.q{font-weight:600}
.ans{color:var(--text-2);font-size:13.5px;margin-top:4px}
.ex{font-size:13px;color:var(--text-2);border-left:2px solid var(--border);padding-left:8px;margin-top:6px}
.ex b{color:var(--text);font-weight:600}.ex .a{color:var(--muted)}
details summary{cursor:pointer;color:var(--s1);font-size:13px;margin-top:6px}
.dist{display:flex;height:22px;gap:2px;border-radius:4px;overflow:hidden;margin:10px 0 6px}
.dist span{display:block;height:100%}
.warn{color:var(--warn)}.bad{color:var(--bad)}.good{color:var(--good)}
.empty{color:var(--muted);font-size:14px}
footer{color:var(--muted);font-size:12px;text-align:center;margin-top:32px}
"""


def render_report_html(report: DailyQuestionReport) -> bytes:
    day = report.day.day.strftime("%d.%m.%Y")
    generated = report.generated_at.astimezone(report.day.timezone)
    parts = [
        "<!doctype html><html lang='ru'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        f"<title>Поддержка — {day}</title><style>{_STYLE}</style></head><body><main class='wrap'>",
        f"<h1>Поддержка — {day}</h1>",
        f"<p class='sub'>Вопросы, типовые запросы и время ответа по вашим беседам за день. "
        f"Часовой пояс {escape(report.day.timezone.key)}.</p>",
        _kpis(report),
        _categories(report.categories, report.requests, report.classified),
        _intents(report.intents, report.requests),
        _other_topics(report.other_topics),
        _response(report.response, report.hourly),
        _activity(report.hourly),
        _chats(report.chats),
        _longest_waits(report),
        _definitions(),
        f"<footer>Сформировано {generated:%d.%m.%Y %H:%M}</footer>",
        "</main></body></html>",
    ]
    return "".join(parts).encode("utf-8")


# --- блоки ------------------------------------------------------------------


def _kpis(report: DailyQuestionReport) -> str:
    response = report.response
    classified = _percent(report.classified, report.requests)
    items = [
        (_number(report.requests), "обращений",
         f"уточнений {report.clarifications} · напоминаний {report.reminders}"),
        (format_duration(response.median), "медиана первого ответа",
         f"в рабочее время {format_duration(response.median_work)}"),
        (format_duration(response.p90), "90-й перцентиль",
         "10% самых долгих ожиданий дольше"),
        (_share(response.within_15_work), "ответили за 15 минут", "вопросы в рабочее время"),
        (str(response.unanswered), "без ответа на конец дня",
         "клиент ждал ответа, когда день закончился"),
        (_share(report.off_hours_share), "сообщений вне рабочего времени", "Пн–Пт 09:00–20:00"),
        (str(report.conversations), "бесед с клиентами",
         f"сообщений: клиентов {report.client_messages}, поддержки {report.support_messages}"),
        (classified, "обращений с определённым типом", "остальные — в «Прочих темах»"),
    ]
    cells = "".join(
        f"<div class='card kpi'><div class='v'>{escape(value)}</div>"
        f"<div class='l'>{label}</div><div class='d'>{escape(detail)}</div></div>"
        for value, label, detail in items
    )
    return f"<section class='kpis'>{cells}</section>"


def _categories(categories: list[CategoryStat], requests: int, classified: int) -> str:
    head = "<h2>Категории запросов</h2>"
    if not categories:
        return head + _empty("Ни одно обращение не удалось отнести к категории.")
    peak = max(c.requests for c in categories)
    rows = "".join(
        f"<tr><td>{_category(c.key, c.title)}</td>"
        f"<td class='n'>{c.requests}</td><td class='n'>{_percent(c.requests, requests)}</td>"
        f"<td class='n'>{c.clients}</td>"
        f"<td style='width:35%'><div class='bar' style='width:{c.requests * 100 / peak:.0f}%;"
        f"background:var({_CATEGORY_COLORS.get(c.key, '--s1')})'></div></td></tr>"
        for c in categories
    )
    unclassified = requests - classified
    tail = (
        f"<p class='note'>Без категории: {unclassified} — см. «Прочие темы».</p>" if unclassified else ""
    )
    return (
        head + "<p class='note'>По классификации поддержки Dots. Доля — от всех обращений за день.</p>"
        "<div class='card scroll'><table><tr><th>Категория</th><th class='n'>Обращений</th>"
        f"<th class='n'>Доля</th><th class='n'>Клиентов</th><th></th></tr>{rows}</table>{tail}</div>"
    )


def _intents(intents: list[IntentStat], requests: int) -> str:
    head = "<h2>Топ запросов</h2>"
    if not intents:
        return head + _empty("Типовых запросов за день не найдено.")
    rows = []
    for rank, intent in enumerate(intents[:TOP_INTENTS], start=1):
        examples = "".join(
            f"<div class='ex'><b>Клиент:</b> «{escape(_shorten(e.question))}»<br>"
            + (
                f"<span class='a'>Поддержка: «{escape(_shorten(e.answer))}»</span>"
                if e.answer
                else "<span class='a warn'>Поддержка не ответила по существу</span>"
            )
            + "</div>"
            for e in intent.examples
        )
        counts = (
            f"{_requests(intent.requests)} · {_percent(intent.requests, requests)} · {_clients(intent.clients)}"
            + (f" · {_clarifications(intent.clarifications)}" if intent.clarifications else "")
        )
        rows.append(
            f"<tr><td class='n'>{rank}</td><td>"
            f"<div class='q'>{escape(intent.title)}</div>"
            f"<span class='chip'>{escape(intent.category_title)}</span>"
            f"<span class='note'>{counts}</span>"
            + examples
            + "<details><summary>Типовой ответ из базы знаний</summary>"
            f"<div class='ans'>{escape(intent.standard_answer)}</div></details>"
            + "</td></tr>"
        )
    return (
        head + "<p class='note'>Под каждым типом — реальные вопросы клиентов и ответы вашей поддержки "
        "(телефоны, почта и пароли скрыты). Типовой ответ — справка из базы знаний поддержки Dots, "
        "в переписке его могло не быть.</p>"
        f"<div class='card'><table>{''.join(rows)}</table></div>"
    )


def _other_topics(clusters: list[QuestionCluster]) -> str:
    """Темы из нескольких обращений — таблицей, одиночные обращения — свёрнутым списком."""
    if not clusters:
        return ""
    groups = [c for c in clusters if c.requests > 1]
    singles = [c for c in clusters if c.requests == 1]
    parts = [
        "<h2>Прочие темы</h2><p class='note'>Обращения, которые не удалось отнести к типовым запросам, "
        "сгруппированы по смыслу.</p><div class='card scroll'>"
    ]
    if groups:
        rows = "".join(
            f"<tr><td>{escape(c.label.capitalize())}</td><td class='n'>{c.requests}</td>"
            f"<td class='n'>{c.count}</td>"
            f"<td class='note'>«{escape(_shorten(c.representative_question))}»</td></tr>"
            for c in groups
        )
        parts.append(
            "<table><tr><th>Тема</th><th class='n'>Обращений</th><th class='n'>Клиентов</th>"
            f"<th>Пример</th></tr>{rows}</table>"
        )
    if singles:
        quotes = "".join(f"<div class='ex'>«{escape(_shorten(c.representative_question))}»</div>" for c in singles)
        parts.append(f"<details><summary>Единичные обращения: {len(singles)}</summary>{quotes}</details>")
    parts.append("</div>")
    return "".join(parts)


def _response(response: ResponseStats, hourly: list[HourActivity]) -> str:
    total = sum(count for _, count in response.buckets)
    if not total and not response.unanswered:
        return ""
    segments = "".join(
        f"<span style='flex:{count};background:var({color})' title='{label}: {count}'></span>"
        for (label, count), color in zip(response.buckets, _BUCKET_COLORS)
        if count
    )
    legend = "".join(
        f"<span><i style='background:var({color})'></i>{label} — {count}</span>"
        for (label, count), color in zip(response.buckets, _BUCKET_COLORS)
    )
    summary = (
        f"Медиана {format_duration(response.median)}, среднее {format_duration(response.average)}, "
        f"90-й перцентиль {format_duration(response.p90)}. В рабочее время: медиана "
        f"{format_duration(response.median_work)}, 90-й перцентиль {format_duration(response.p90_work)}; "
        f"вне рабочего времени медиана {format_duration(response.median_off)}."
    )
    distribution = (
        "<div class='card'><b>Как быстро клиенты получают первый ответ</b>"
        + (f"<div class='dist'>{segments}</div>" if total else "")
        + f"<div class='legend'>{legend}</div><p class='note'>{summary}</p></div>"
    )
    return "<h2>Время ответа</h2><div class='grid2'>" + distribution + _fast_by_hour(hourly) + "</div>"


def _fast_by_hour(hourly: list[HourActivity]) -> str:
    hours = [h for h in hourly if h.asked]
    if not hours:
        return ""
    width, height, bottom = 480, 170, 150
    step = width / len(hours)
    bars = []
    for i, h in enumerate(hours):
        share = h.answered_in_15 / h.asked
        bar_height = share * (bottom - 20)
        color = "--good" if share >= 0.9 else "--c4" if share >= 0.6 else "--bad"
        x = i * step + step * 0.15
        bars.append(
            f"<rect x='{x:.1f}' y='{bottom - bar_height:.1f}' width='{step * 0.7:.1f}' "
            f"height='{bar_height:.1f}' rx='2' fill='var({color})'>"
            f"<title>{h.hour:02d}:00 — {h.answered_in_15} из {h.asked} за 15 мин</title></rect>"
            f"<text x='{x + step * 0.35:.1f}' y='{bottom - bar_height - 4:.1f}' text-anchor='middle'>"
            f"{round(share * 100)}%</text>"
            f"<text x='{x + step * 0.35:.1f}' y='{bottom + 16}' text-anchor='middle'>{h.hour:02d}</text>"
        )
    return (
        "<div class='card'><b>Ответили за 15 минут — по часу, когда написал клиент</b>"
        f"<svg viewBox='0 0 {width} {height + 10}' role='img' aria-label='Ответы за 15 минут по часам'>"
        f"{''.join(bars)}</svg></div>"
    )


def _activity(hourly: list[HourActivity]) -> str:
    peak = max((max(h.client_messages, h.support_messages) for h in hourly), default=0)
    if not peak:
        return ""
    width, bottom, top = 720, 150, 10
    slot = width / 24
    bars = []
    for h in hourly:
        x = h.hour * slot
        for offset, value, color, who in (
            (0.12, h.client_messages, "--s1", "клиенты"),
            (0.5, h.support_messages, "--s2", "поддержка"),
        ):
            bar_height = value / peak * (bottom - top)
            bars.append(
                f"<rect x='{x + slot * offset:.1f}' y='{bottom - bar_height:.1f}' width='{slot * 0.36:.1f}' "
                f"height='{bar_height:.1f}' rx='2' fill='var({color})'>"
                f"<title>{h.hour:02d}:00 — {who}: {value}</title></rect>"
            )
        if h.hour % 3 == 0:
            bars.append(f"<text x='{x + slot / 2:.1f}' y='{bottom + 16}' text-anchor='middle'>{h.hour:02d}</text>")
    return (
        "<h2>Когда писали</h2><div class='card'><b>Сообщения по часам</b>"
        "<div class='legend'><span><i style='background:var(--s1)'></i>клиенты</span>"
        "<span><i style='background:var(--s2)'></i>поддержка</span></div>"
        f"<svg viewBox='0 0 {width} {bottom + 22}' role='img' aria-label='Сообщения по часам'>"
        f"{''.join(bars)}</svg></div>"
    )


def _chats(chats: list[ChatStat]) -> str:
    if not chats:
        return ""
    rows = "".join(
        f"<tr><td>{escape(c.title)}</td><td class='n'>{c.client_messages}</td>"
        f"<td class='n'>{c.requests}</td><td class='n'>{c.answered}</td>"
        f"<td class='n{' bad' if c.unanswered else ''}'>{c.unanswered}</td>"
        f"<td class='n'>{format_duration(c.median)}</td></tr>"
        for c in chats
    )
    return (
        "<h2>По беседам</h2><div class='card scroll'><table><tr><th>Беседа</th>"
        "<th class='n'>Сообщений клиентов</th><th class='n'>Обращений</th><th class='n'>Отвечено</th>"
        f"<th class='n'>Без ответа</th><th class='n'>Медиана ответа</th></tr>{rows}</table></div>"
    )


def _longest_waits(report: DailyQuestionReport) -> str:
    if not report.longest_waits:
        return ""
    timezone = report.day.timezone
    rows = "".join(
        f"<tr><td>{escape(w.chat_title)}</td><td class='n'>{w.asked_at.astimezone(timezone):%H:%M}</td>"
        f"<td class='n'>{format_duration(w.waited)}</td>"
        f"<td>{'' if w.answered else '<span class=\"bad\">без ответа</span>'}</td></tr>"
        for w in report.longest_waits
    )
    return (
        "<h2>Самые долгие ожидания</h2><div class='card scroll'><table><tr><th>Беседа</th>"
        f"<th class='n'>Вопрос в</th><th class='n'>Ждали</th><th></th></tr>{rows}</table></div>"
    )


def _definitions() -> str:
    return (
        "<h2>Как считается</h2><div class='card note'>"
        "<p><b>Поддержка</b> — администраторы беседы и тот, кто добавил бота; <b>клиенты</b> — остальные.</p>"
        "<p><b>Обращение</b> — новый запрос клиента: вопрос, просьба или скриншот без подписи. "
        "Несколько сообщений подряд с паузой до 2 минут и без ответа поддержки между ними — одна реплика. "
        "Приветствия, благодарности и «ок» не считаются.</p>"
        "<p><b>Уточнение</b> — реплика, которая продолжает прошлый запрос того же клиента: ответ через reply, "
        "«а если…», «не получилось», вопрос без своей темы или на ту же тему в течение 2 часов. "
        "«Ещё вопрос», «и ещё…» — всегда новый запрос. <b>Напоминание</b> — «вы тут?», «есть новости?».</p>"
        "<p><b>Тип запроса</b> определяется по классификации поддержки Dots (14 категорий, 90 типов) "
        "моделью, обученной на размеченных вопросах, без LLM. Если уверенности мало, обращение попадает "
        "в «Прочие темы», где группируется по смыслу.</p>"
        "<p><b>Время ответа</b> — от вопроса клиента до первого ответа поддержки по существу; "
        "приветствия и «секунду, уточню» ответом не считаются. Это первая реакция, а не решение вопроса. "
        "<b>Рабочее время</b> — Пн–Пт 09:00–20:00.</p></div>"
    )


# --- форматирование ---------------------------------------------------------


def format_duration(value: timedelta | None) -> str:
    if value is None:
        return "—"
    minutes = int(value.total_seconds() // 60)
    if minutes < 1:
        return "< 1 мин"
    if minutes < 60:
        return f"{minutes} мин"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} ч {minutes} мин" if minutes else f"{hours} ч"


def _category(key: str, title: str) -> str:
    return f"<span class='cat'><i style='background:var({_CATEGORY_COLORS.get(key, '--s1')})'></i>{escape(title)}</span>"


def _empty(text: str) -> str:
    return f"<div class='card empty'>{text}</div>"


def _number(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def _percent(part: int, total: int) -> str:
    return f"{round(part * 100 / total)}%" if total else "—"


def _share(value: float | None) -> str:
    return "—" if value is None else f"{round(value * 100)}%"


def _requests(count: int) -> str:
    return f"{count} {_plural(count, 'обращение', 'обращения', 'обращений')}"


def _clarifications(count: int) -> str:
    return f"{count} {_plural(count, 'уточнение', 'уточнения', 'уточнений')}"


def _clients(count: int) -> str:
    return f"{count} {_plural(count, 'клиент', 'клиента', 'клиентов')}"


def _plural(count: int, one: str, few: str, many: str) -> str:
    if count % 10 == 1 and count % 100 != 11:
        return one
    if count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
        return few
    return many


def _shorten(text: str, limit: int = 220) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"
