import pytest

from infrastructure.nlp.heuristic_message_classifier import HeuristicMessageClassifier

classifier = HeuristicMessageClassifier()


@pytest.mark.parametrize(
    "text",
    [
        "Привет", "Здравствуйте!", "Добрый день)", "Доброго дня", "Вітаю", "Добрий день!",
        "Спасибо", "Спасибо большое!", "Дякую", "Дуже дякую", "ок", "Окей", "+", "👍", "?",
        "Понятно, спасибо", "Зрозуміло, дякую", "Хорошо", "Добре",
    ],
)
def test_trivial(text):
    assert classifier.is_trivial(text)


@pytest.mark.parametrize(
    "text",
    ["Добрый день, не приходит смс", "Привіт, як змінити картку?", "оплата не проходит", "Дякую, а коли доставка?"],
)
def test_substantive_is_not_trivial(text):
    assert not classifier.is_trivial(text)


@pytest.mark.parametrize(
    "text",
    [
        "Секунду, уточню", "Здравствуйте! Минутку, сейчас проверю", "Уточняю", "Одну минуту",
        "Хвилинку, уточню", "Зачекайте, будь ласка, перевірю", "Добрий день, секундочку",
    ],
)
def test_holding_reply(text):
    assert classifier.is_holding_reply(text)


@pytest.mark.parametrize(
    "text",
    [
        "Здравствуйте! Способ оплаты меняется в разделе Профиль → Оплата.",
        "Уточните, пожалуйста, номер заказа",  # просьба к клиенту — уже ответ по существу
        "Перевірила: смс відправлено повторно, перевірте телефон",
        "Привет",  # приветствие — не «уточню», оно отсеивается как пустая реплика
    ],
)
def test_real_answer_is_not_holding(text):
    assert not classifier.is_holding_reply(text)


@pytest.mark.parametrize(
    "text",
    [
        "Как изменить способ оплаты?",
        "как поменять способ оплаты",
        "Можно отменить бронь",
        "Не приходит смс с кодом",
        "Хочу скасувати бронювання",
        "Чи можна змінити картку",
        "не працює додаток",
        "ошибка при оплате",
    ],
)
def test_question(text):
    assert classifier.is_question(text)


@pytest.mark.parametrize("text", ["Добрий день", "Спасибо!", "Отправил скрин", "Ок, жду"])
def test_not_question(text):
    assert not classifier.is_question(text)
