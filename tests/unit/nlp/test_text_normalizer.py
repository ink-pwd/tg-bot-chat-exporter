import pytest

from infrastructure.nlp.lemmatizer import looks_ukrainian

PAYMENT_CHANGE = ["#change", "#method", "#payment"]


@pytest.mark.parametrize(
    "text",
    [
        "Как изменить способ оплаты?",
        "как поменять способ оплаты?",
        "Можно изменить способ оплаты?",
        "а где сменить способ оплаты?",
        "Подскажите, пожалуйста, как изменить способ оплаты?",
        "Як змінити спосіб оплати?",
        "Добрий день, як поміняти спосіб оплати?",
        "Здравствуйте, как изменить метод оплаты?",
    ],
)
def test_same_request_in_russian_and_ukrainian_gives_same_concepts(normalizer, text):
    assert sorted(normalizer.normalize(text).tokens) == PAYMENT_CHANGE


def test_card_variants(normalizer):
    for text in ("Где поменять карту для оплаты?", "Де змінити картку для оплати?"):
        assert sorted(normalizer.normalize(text).tokens) == ["#card", "#change", "#payment"]


def test_greetings_and_polite_words_are_removed(normalizer):
    assert normalizer.normalize("Добрый день! Подскажите, пожалуйста, спасибо").tokens == []
    assert normalizer.normalize("Добрий день, підкажіть, будь ласка, дякую").tokens == []


def test_numbers_are_unified(normalizer):
    first = normalizer.normalize("Где заказ 12345?").tokens
    second = normalizer.normalize("Где заказ 98?").tokens

    assert first == second == ["#order", "<num>"]


def test_links_and_mentions_are_dropped(normalizer):
    assert normalizer.normalize("смотрите https://example.com/pay @support").tokens == ["#view"]


def test_ukrainian_without_special_letters_is_detected(normalizer):
    # «повернуть» — по-русски «повернуть (руль)», по-украински «вернут»
    assert normalizer.normalize("Коли повернуть кошти?").tokens == ["#refund", "#money"]


def test_cognates_outside_dictionary_are_folded(normalizer):
    ukrainian = normalizer.normalize("Де подивитися історію платежів?").tokens
    russian = normalizer.normalize("Где посмотреть историю платежей?").tokens

    assert sorted(ukrainian) == sorted(russian) == ["#payment", "#view", "история"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Як змінити картку?", True),
        ("Коли повернуть кошти", True),
        ("Чи можна оплатити", True),
        ("Как изменить карту?", False),
        ("Где мой заказ", False),
    ],
)
def test_language_detection(text, expected):
    assert looks_ukrainian(text.lower()) is expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("как изменить спосб оплаты", PAYMENT_CHANGE),
        ("как изменить способ оплатты", PAYMENT_CHANGE),
        ("як змінити спосиб оплати", PAYMENT_CHANGE),
        ("не приходит смсс", ["#receive", "#sms"]),
    ],
)
def test_typos_in_dictionary_words_are_corrected(normalizer, text, expected):
    assert sorted(normalizer.normalize(text).tokens) == expected


def test_known_words_are_not_corrected(normalizer):
    # «способный» — настоящее слово, не опечатка в «способ»
    assert "#method" not in normalizer.normalize("способный сотрудник").tokens
