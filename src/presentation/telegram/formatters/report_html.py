"""HTML-отчёт по поддержке за день.

Один самодостаточный файл: стили внутри, графики — встроенный SVG, без JavaScript
и внешних ресурсов. Открывается офлайн в браузере и в просмотрщике Telegram.
Весь текст из переписок экранируется: сообщение клиента не должно стать разметкой.
"""
from datetime import timedelta
from html import escape

from application.dto.report import DailyQuestionReport, HourActivity, ResponseStats
from domain.entities.question_cluster import QuestionCluster

TOP_QUESTIONS = 3

_STYLE = """
:root{--bg:#f6f7f9;--card:#fff;--text:#1d2430;--muted:#6b7380;--line:#e3e6ea;
--client:#3b82f6;--support:#10b981;--warn:#f59e0b;--bar:#94a3b8}
@media (prefers-color-scheme:dark){:root{--bg:#14171c;--card:#1d2128;--text:#e6e9ee;
--muted:#9aa3ae;--line:#2c323b;--bar:#64748b}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif}
main{max-width:860px;margin:0 auto;padding:24px 16px 48px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:0 0 12px}
.sub{color:var(--muted);margin:0 0 20px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin:0 0 16px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:0 0 16px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.kpi b{display:block;font-size:24px;line-height:1.2}.kpi span{color:var(--muted);font-size:13px}
.topic{display:flex;gap:14px;padding:12px 0;border-top:1px solid var(--line)}
.topic:first-of-type{border-top:0;padding-top:0}
.rank{flex:none;width:32px;height:32px;border-radius:50%;background:var(--client);color:#fff;
display:flex;align-items:center;justify-content:center;font-weight:600}
.topic h3{margin:0;font-size:16px}.count{color:var(--muted);font-size:14px}
.quote{margin:6px 0 0;font-style:italic}
.examples{margin:6px 0 0;padding-left:18px;color:var(--muted);font-size:14px}
.legend{display:flex;gap:16px;color:var(--muted);font-size:13px;margin:4px 0 0}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px}
svg{display:block;width:100%;height:auto}svg text{fill:var(--muted);font-size:11px}
table{width:100%;border-collapse:collapse;font-size:14px}
td,th{text-align:left;padding:6px 4px;border-top:1px solid var(--line)}th{color:var(--muted);font-weight:500}
details summary{cursor:pointer;font-weight:600}details[open] summary{margin-bottom:10px}
.muted{color:var(--muted)}.warn{color:var(--warn)}
footer{color:var(--muted);font-size:12px;text-align:center;margin-top:24px}
"""


def render_report_html(report: DailyQuestionReport) -> bytes:
    day = report.day.day.strftime("%d.%m.%Y")
    title = f"Поддержка — {escape(report.account_name)} — {day}"
    parts = [
        "<!doctype html><html lang='ru'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        f"<title>{title}</title><style>{_STYLE}</style></head><body><main>",
        f"<h1>📊 {escape(report.account_name)} — {day}</h1>",
        f"<p class='sub'>Часовой пояс {escape(report.day.timezone.key)}</p>",
        _kpis(report),
        _top_questions(report.clusters),
        _hourly_chart(report.hourly),
        _response_chart(report.response),
        _other_topics(report.clusters),
        _longest_waits(report),
        _method_note(),
        f"<footer>Сформировано {report.generated_at.astimezone(report.day.timezone):%d.%m.%Y %H:%M}</footer>",
        "</main></body></html>",
    ]
    return "".join(parts).encode("utf-8")


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


def _kpis(report: DailyQuestionReport) -> str:
    response = report.response
    items = [
        (f"{report.requests:,}".replace(",", " "), "обращений"),
        (f"{report.questions:,}".replace(",", " "), "вопросов"),
        (str(report.conversations), "диалогов"),
        (format_duration(response.median), "медиана ответа"),
        (format_duration(response.average), "среднее время ответа"),
        (str(response.unanswered), "без ответа на конец дня"),
    ]
    cells = "".join(f"<div class='kpi'><b>{escape(value)}</b><span>{label}</span></div>" for value, label in items)
    return f"<section class='kpis'>{cells}</section>"


def _top_questions(clusters: list[QuestionCluster]) -> str:
    if not clusters:
        return "<section class='card'><h2>Топ запросов</h2><p class='muted'>Вопросов от клиентов за день не найдено.</p></section>"
    total = sum(c.count for c in clusters) or 1
    rows = []
    for rank, cluster in enumerate(clusters[:TOP_QUESTIONS], start=1):
        examples = "".join(f"<li>{escape(_shorten(text))}</li>" for text in cluster.examples[:2])
        rows.append(
            "<div class='topic'>"
            f"<div class='rank'>{rank}</div><div>"
            f"<h3>{escape(cluster.label.capitalize())}</h3>"
            f"<div class='count'>{_clients(cluster.count)} · {round(cluster.count * 100 / total)}% вопросов</div>"
            f"<p class='quote'>«{escape(_shorten(cluster.representative_question))}»</p>"
            + (f"<ul class='examples'>{examples}</ul>" if examples else "")
            + "</div></div>"
        )
    return f"<section class='card'><h2>Топ запросов</h2>{''.join(rows)}</section>"


def _hourly_chart(hourly: list[HourActivity]) -> str:
    width, height, top, bottom = 720, 180, 10, 22
    peak = max((h.client_messages + h.support_messages for h in hourly), default=0) or 1
    slot = width / 24
    bar = slot * 0.34
    bars = []
    for activity in hourly:
        x = activity.hour * slot + slot * 0.14
        for offset, value, color in (
            (0, activity.client_messages, "var(--client)"),
            (bar + 1, activity.support_messages, "var(--support)"),
        ):
            h = (height - top - bottom) * value / peak
            y = height - bottom - h
            bars.append(
                f"<rect x='{x + offset:.1f}' y='{y:.1f}' width='{bar:.1f}' height='{h:.1f}' rx='2' fill='{color}'>"
                f"<title>{activity.hour:02d}:00 — {value}</title></rect>"
            )
        if activity.hour % 3 == 0:
            bars.append(
                f"<text x='{activity.hour * slot + slot / 2:.1f}' y='{height - 6}' text-anchor='middle'>{activity.hour:02d}</text>"
            )
    legend = (
        "<div class='legend'><span><i style='background:var(--client)'></i>клиенты</span>"
        "<span><i style='background:var(--support)'></i>поддержка</span></div>"
    )
    return (
        "<section class='card'><h2>Сообщения по часам</h2>"
        f"<svg viewBox='0 0 {width} {height}' role='img' aria-label='Сообщения по часам'>{''.join(bars)}</svg>"
        f"{legend}</section>"
    )


def _response_chart(response: ResponseStats) -> str:
    if response.answered == 0:
        return ""
    width, row = 720, 26
    label_width = 110
    peak = max(count for _, count in response.buckets) or 1
    rows = []
    for index, (label, count) in enumerate(response.buckets):
        y = index * row
        w = (width - label_width - 50) * count / peak
        rows.append(
            f"<text x='0' y='{y + 17}'>{escape(label)}</text>"
            f"<rect x='{label_width}' y='{y + 5}' width='{w:.1f}' height='16' rx='3' fill='var(--bar)'></rect>"
            f"<text x='{label_width + w + 6:.1f}' y='{y + 17}'>{count}</text>"
        )
    height = row * len(response.buckets)
    return (
        "<section class='card'><h2>Время ответа</h2>"
        f"<svg viewBox='0 0 {width} {height}' role='img' aria-label='Время ответа'>{''.join(rows)}</svg>"
        f"<p class='muted'>Отвечено {response.answered}, без ответа на конец дня {response.unanswered}.</p></section>"
    )


def _other_topics(clusters: list[QuestionCluster]) -> str:
    rest = clusters[TOP_QUESTIONS:]
    if not rest:
        return ""
    rows = "".join(
        f"<tr><td>{rank}</td><td>{escape(c.label.capitalize())}</td><td>{c.count}</td>"
        f"<td class='muted'>«{escape(_shorten(c.representative_question))}»</td></tr>"
        for rank, c in enumerate(rest, start=TOP_QUESTIONS + 1)
    )
    return (
        "<section class='card'><details><summary>Остальные темы</summary>"
        f"<table><tr><th>#</th><th>Тема</th><th>Клиентов</th><th>Пример</th></tr>{rows}</table>"
        "</details></section>"
    )


def _longest_waits(report: DailyQuestionReport) -> str:
    if not report.longest_waits:
        return ""
    tz = report.day.timezone
    rows = "".join(
        f"<tr><td>{escape(_shorten(w.chat_title, 40))}</td><td>{w.asked_at.astimezone(tz):%H:%M}</td>"
        f"<td>{format_duration(w.waited)}</td>"
        f"<td>{'ответили' if w.answered else '<span class=warn>без ответа</span>'}</td></tr>"
        for w in report.longest_waits
    )
    return (
        "<section class='card'><details><summary>Самые долгие ожидания</summary>"
        f"<table><tr><th>Чат</th><th>Вопрос в</th><th>Ждали</th><th></th></tr>{rows}</table>"
        "</details></section>"
    )


def _method_note() -> str:
    return (
        "<section class='card muted'><details><summary>Как считается</summary>"
        "<p><b>Обращение</b> — содержательное сообщение клиента; новое начинается после паузы больше 3 часов. "
        "Приветствия, благодарности и «ок» не считаются.</p>"
        "<p><b>Время ответа</b> — от вопроса клиента до первого ответа поддержки по существу. "
        "Приветствия и «секунду, уточню» ответом не считаются.</p>"
        "<p><b>Темы</b> собираются по смыслу (русский и украинский), а не по точному тексту; "
        "в теме считаются разные клиенты, а не сообщения.</p>"
        "</details></section>"
    )


def _clients(count: int) -> str:
    if count % 10 == 1 and count % 100 != 11:
        word = "клиент"
    elif count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
        word = "клиента"
    else:
        word = "клиентов"
    return f"{count} {word}"


def _shorten(text: str, limit: int = 160) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"
