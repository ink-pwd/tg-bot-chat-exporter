import random

import pytest

from domain.entities.question_cluster import ClientQuestion
from tests.unit.nlp.question_samples import PAYMENT_METHOD, TOPICS


def as_questions(texts: list[str]) -> list[ClientQuestion]:
    return [ClientQuestion(text, (index, index)) for index, text in enumerate(texts)]


def test_original_examples_form_one_group(clusterer):
    texts = [
        "Как изменить способ оплаты?",
        "как поменять способ оплаты?",
        "Можно изменить способ оплаты?",
        "а где сменить способ оплаты?",
    ]

    clusters = clusterer.cluster(as_questions(texts))

    assert len(clusters) == 1
    assert clusters[0].count == 4


def test_all_payment_method_variants_form_one_group(clusterer):
    clusters = clusterer.cluster(as_questions(PAYMENT_METHOD))

    assert len(clusters) == 1
    assert clusters[0].count == len(PAYMENT_METHOD)


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_every_topic_is_one_group_and_topics_do_not_mix(clusterer, seed):
    labelled = [(topic, text) for topic, texts in TOPICS.items() for text in texts]
    random.Random(seed).shuffle(labelled)
    topic_of = {text: topic for topic, text in labelled}

    clusters = clusterer.cluster(as_questions([text for _, text in labelled]))

    groups = [{topic_of[t] for t in [c.representative_question, *c.examples]} for c in clusters]
    assert all(len(topics) == 1 for topics in groups), "темы смешались"
    assert sorted(next(iter(t)) for t in groups) == sorted(TOPICS), "тема разбилась на части"


def test_count_is_distinct_clients(clusterer):
    same_client = (1, 42)
    questions = [
        ClientQuestion("Не приходит смс с кодом", same_client),
        ClientQuestion("смс так и не пришло", same_client),
        ClientQuestion("Не приходить смс з кодом", (2, 7)),
    ]

    clusters = clusterer.cluster(questions)

    assert [c.count for c in clusters] == [2]


def test_clusters_are_sorted_by_count(clusterer):
    texts = ["Как отменить бронь?"] + ["Як змінити спосіб оплати?", "Как поменять способ оплаты?"]

    clusters = clusterer.cluster(as_questions(texts))

    assert [c.count for c in clusters] == [2, 1]


def test_representative_is_short_real_question(clusterer):
    clusters = clusterer.cluster(as_questions(PAYMENT_METHOD))

    representative = clusters[0].representative_question
    assert representative in PAYMENT_METHOD
    assert len(representative) <= 30


def test_label_uses_concepts(clusterer):
    clusters = clusterer.cluster(as_questions(PAYMENT_METHOD))

    assert set(clusters[0].label.split(" · ")) == {"изменить", "оплата", "способ"}


def test_questions_without_meaning_are_skipped(clusterer):
    assert clusterer.cluster(as_questions(["Добрый день!", "Дякую", "?"])) == []


def test_single_question(clusterer):
    clusters = clusterer.cluster(as_questions(["Як скасувати бронювання?"]))

    assert len(clusters) == 1 and clusters[0].count == 1


def test_order_numbers_do_not_appear_in_label(clusterer):
    clusters = clusterer.cluster(as_questions(["Как отменить бронь 123?", "Хочу отменить бронь 456"]))

    assert "<num>" not in clusters[0].label


def test_label_prefers_dictionary_concepts_over_plain_words(clusterer):
    clusters = clusterer.cluster(
        as_questions(["хочу поміняти склад замовлення", "Как изменить заказ?", "Як змінити замовлення?"])
    )

    assert set(clusters[0].label.split(" · ")) == {"заказ", "изменить"}
