"""Группировка запросов по смыслу: TF-IDF + косинусная близость + иерархическая кластеризация.

Признаки двух видов:
- понятия и леммы (и их пары) — смысл запроса после словаря синонимов;
- кусочки слов по 3–5 букв — ловят формы слов и близкие слова вне словаря.

Сравниваются уникальные смыслы, а не сообщения: «Как изменить способ оплаты?»
от 50 клиентов — одна точка. Так матрица попарных сравнений остаётся небольшой.
"""
from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np
from scipy.sparse import hstack
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from domain.entities.question_cluster import ClientQuestion, QuestionCluster
from infrastructure.nlp.text_normalizer import (
    CONCEPT_PREFIX,
    NUMBER_TOKEN,
    NormalizedText,
    TextNormalizer,
)

# уникальных смыслов больше этого — редкие отбрасываются (матрица n×n растёт квадратично)
MAX_UNIQUE_MEANINGS = 3000

# смыслы, почти такие же типичные, как самый типичный, — из них берём лучшую формулировку
_CENTRALITY_TOLERANCE = 0.05


@dataclass
class _Meaning:
    """Уникальный смысл и все вопросы с ним."""

    tokens: list[str]
    questions: list[tuple[ClientQuestion, NormalizedText]] = field(default_factory=list)


class TfidfQuestionClusterer:
    def __init__(
        self,
        normalizer: TextNormalizer,
        concept_labels: dict[str, str],
        *,
        # подобран на tests/unit/nlp/question_samples.py: темы собираются верно при 0.75–0.85
        distance_threshold: float = 0.8,
        char_weight: float = 0.5,
        examples: int = 3,
    ) -> None:
        self._normalizer = normalizer
        self._concept_labels = concept_labels
        self._distance_threshold = distance_threshold
        self._char_weight = char_weight
        self._examples = examples

    def cluster(self, questions: list[ClientQuestion]) -> list[QuestionCluster]:
        meanings = self._meanings(questions)
        if not meanings:
            return []

        if len(meanings) == 1:
            groups = [[0]]
            similarity = np.ones((1, 1), dtype=np.float32)
            word_features, vocabulary = None, None
        else:
            features, word_features, vocabulary = self._features([m.tokens for m in meanings])
            similarity = (features @ features.T).toarray().astype(np.float32)
            np.clip(similarity, 0.0, 1.0, out=similarity)
            labels = AgglomerativeClustering(
                n_clusters=None,
                metric="precomputed",
                linkage="average",
                distance_threshold=self._distance_threshold,
            ).fit_predict(1.0 - similarity)
            by_label: dict[int, list[int]] = defaultdict(list)
            for index, label in enumerate(labels):
                by_label[label].append(index)
            groups = list(by_label.values())

        clusters = [
            self._build(
                [meanings[i] for i in group],
                similarity[np.ix_(group, group)],
                word_features[group] if word_features is not None else None,
                vocabulary,
            )
            for group in groups
        ]
        clusters.sort(key=lambda c: (-c.count, c.label))
        return clusters

    def _meanings(self, questions: list[ClientQuestion]) -> list[_Meaning]:
        by_key: dict[str, _Meaning] = {}
        for question in questions:
            normalized = self._normalizer.normalize(question.text)
            if not normalized.tokens:
                continue
            meaning = by_key.setdefault(normalized.key, _Meaning(sorted(set(normalized.tokens))))
            meaning.questions.append((question, normalized))
        meanings = sorted(by_key.values(), key=lambda m: -len(m.questions))
        return meanings[:MAX_UNIQUE_MEANINGS]

    def _features(self, token_lists: list[list[str]]):
        words = TfidfVectorizer(analyzer=_tokens_and_pairs, sublinear_tf=True, dtype=np.float32)
        word_matrix = words.fit_transform(token_lists)
        chars = TfidfVectorizer(
            analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, dtype=np.float32
        )
        char_matrix = chars.fit_transform(
            [" ".join(t.removeprefix(CONCEPT_PREFIX) for t in tokens) for tokens in token_lists]
        )
        combined = normalize(hstack([word_matrix, self._char_weight * char_matrix]).tocsr())
        return combined, word_matrix, words.get_feature_names_out()

    def _build(self, meanings: list[_Meaning], similarity: np.ndarray, word_features, vocabulary) -> QuestionCluster:
        # типичность смысла — средняя близость к остальным с учётом числа вопросов
        weights = np.array([len(m.questions) for m in meanings], dtype=np.float32)
        centrality = similarity @ weights / weights.sum()
        typical = centrality.max() - _CENTRALITY_TOLERANCE

        candidates = [
            (centrality[i] < typical, normalized.had_typos, len(question.text), -centrality[i], question.text.strip())
            for i, meaning in enumerate(meanings)
            for question, normalized in meaning.questions
        ]
        texts: list[str] = []
        for *_, text in sorted(candidates):
            if text not in texts:
                texts.append(text)

        clients = {question.client_id for m in meanings for question, _ in m.questions}
        return QuestionCluster(
            label=self._label(meanings, word_features, vocabulary, weights),
            representative_question=texts[0],
            count=len(clients),
            examples=texts[1 : 1 + self._examples],
        )

    def _label(self, meanings: list[_Meaning], word_features, vocabulary, weights: np.ndarray) -> str:
        if word_features is None:
            top = [t for t in meanings[0].tokens if t != NUMBER_TOKEN][:3]
        else:
            scores = np.asarray(word_features.T @ weights).ravel()
            ranked = [
                vocabulary[i]
                for i in np.argsort(-scores)
                if " " not in vocabulary[i] and vocabulary[i] != NUMBER_TOKEN and scores[i] > 0
            ]
            # понятия из словаря надёжнее отдельных слов: «склад» по-украински — «состав»
            concepts = [t for t in ranked if t.startswith(CONCEPT_PREFIX)][:3]
            top = concepts if len(concepts) >= 2 else ranked[:3]
        return " · ".join(self._display(token) for token in top)

    def _display(self, token: str) -> str:
        if token.startswith(CONCEPT_PREFIX):
            name = token.removeprefix(CONCEPT_PREFIX)
            return self._concept_labels.get(name, name)
        return token


def _tokens_and_pairs(tokens: list[str]) -> list[str]:
    """Понятия/леммы и их пары без учёта порядка: «изменить оплату» = «оплату изменить»."""
    unique = sorted(set(tokens))
    pairs = [f"{a} {b}" for i, a in enumerate(unique) for b in unique[i + 1 :]]
    return unique + pairs
