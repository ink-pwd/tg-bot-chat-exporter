from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from application.dto.report import DailyQuestionReport, HourActivity, LongWait, ResponseStats
from domain.entities.question_cluster import QuestionCluster
from domain.value_objects.day_range import DayRange
from presentation.telegram.formatters.report_html import format_duration, render_report_html

KYIV = ZoneInfo("Europe/Kyiv")


def make_report(clusters=None, answered=10) -> DailyQuestionReport:
    return DailyQuestionReport(
        account_name="Support <Team>",
        day=DayRange(date(2026, 10, 4), KYIV),
        generated_at=datetime(2026, 10, 5, 6, 0, tzinfo=UTC),
        client_messages=1284,
        support_messages=900,
        conversations=218,
        requests=763,
        questions=512,
        response=ResponseStats(
            answered, 6, timedelta(minutes=4), timedelta(minutes=11),
            [("до 5 мин", 6), ("5–15 мин", 2), ("15–60 мин", 1), ("1–3 ч", 1), ("больше 3 ч", 0)],
        ),
        clusters=clusters if clusters is not None else [
            QuestionCluster("изменить · оплата · способ", "Як змінити спосіб оплати?", 47, ["Как поменять карту?"]),
            QuestionCluster("приходит · SMS · код", "Не приходит смс", 31, []),
            QuestionCluster("отмена · бронирование", "Как отменить бронь?", 24, []),
            QuestionCluster("возврат · деньги", "Как вернуть деньги?", 5, []),
        ],
        hourly=[HourActivity(h, h % 5, h % 3) for h in range(24)],
        longest_waits=[LongWait("Иван", datetime(2026, 10, 4, 20, 0, tzinfo=UTC), timedelta(hours=2), False)],
    )


def test_report_contains_key_numbers_and_top_three():
    html = render_report_html(make_report()).decode()

    assert "763" in html and "обращений" in html
    assert "4 мин" in html and "11 мин" in html
    assert "Як змінити спосіб оплати?" in html
    assert "47 клиентов" in html
    assert html.index("Не приходит смс") < html.index("Как отменить бронь?")
    # четвёртая тема — только в свёрнутом списке
    assert "Остальные темы" in html and "Как вернуть деньги?" in html


def test_client_text_is_escaped():
    attack = QuestionCluster("x", "<script>alert(1)</script>", 1, ["<img src=x onerror=alert(1)>"])

    html = render_report_html(make_report(clusters=[attack])).decode()

    assert "<script>alert" not in html
    assert "<img src=x" not in html
    assert "&lt;script&gt;" in html
    assert "Support &lt;Team&gt;" in html


def test_report_is_self_contained():
    html = render_report_html(make_report()).decode()

    assert "<script" not in html
    assert "http://" not in html and "https://" not in html
    assert html.count("<svg") == 2


def test_empty_day_without_questions():
    html = render_report_html(make_report(clusters=[], answered=0)).decode()

    assert "Вопросов от клиентов за день не найдено" in html
    assert html.count("<svg") == 1  # без ответов нет графика времени ответа


def test_format_duration():
    assert format_duration(None) == "—"
    assert format_duration(timedelta(seconds=30)) == "< 1 мин"
    assert format_duration(timedelta(minutes=42)) == "42 мин"
    assert format_duration(timedelta(hours=2)) == "2 ч"
    assert format_duration(timedelta(hours=1, minutes=5)) == "1 ч 5 мин"
