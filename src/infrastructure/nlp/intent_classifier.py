"""Тип запроса по классификации поддержки Dots (taxonomy.toml).

Модель — TF-IDF + логистическая регрессия, обученная заранее скриптом
scripts/train_intent_model.py. В файле модели только словари признаков и веса,
без текстов переписок; загружается без pickle, поэтому не зависит от версии scikit-learn.
На одном и том же тексте всегда даёт один и тот же ответ.
"""
import tomllib
from pathlib import Path

import numpy as np
from scipy.sparse import hstack

from domain.value_objects.request_topic import RequestTopic
from infrastructure.nlp.intent_features import char_vectorizer, model_text, word_vectorizer
from infrastructure.nlp.text_normalizer import RESOURCES, TextNormalizer

MODEL_FILE = RESOURCES / "intent_model.npz"
TAXONOMY_FILE = RESOURCES / "taxonomy.toml"


class ModelIntentClassifier:
    def __init__(
        self,
        normalizer: TextNormalizer,
        *,
        model_file: Path = MODEL_FILE,
        taxonomy_file: Path = TAXONOMY_FILE,
        # подобраны на отложенной части размеченных примеров: тип верен ~80% при этом пороге
        intent_threshold: float = 0.4,
        category_threshold: float = 0.5,
    ) -> None:
        self._normalizer = normalizer
        self._intent_threshold = intent_threshold
        self._category_threshold = category_threshold

        taxonomy = tomllib.loads(taxonomy_file.read_text(encoding="utf-8"))
        self._category_titles: dict[str, str] = taxonomy["categories"]
        self._intents: dict[str, dict] = taxonomy["intents"]

        model = np.load(model_file, allow_pickle=False)
        self._classes = [str(c) for c in model["classes"]]
        self._word = _fitted(word_vectorizer, model["word_terms"], model["word_idf"])
        self._char = _fitted(char_vectorizer, model["char_terms"], model["char_idf"])
        self._coef = model["coef"].astype(np.float32)
        self._intercept = model["intercept"].astype(np.float32)
        categories = [self._intents[c]["category"] for c in self._classes]
        self._category_names = sorted(set(categories))
        self._category_index = np.array([self._category_names.index(c) for c in categories])

    def classify(self, text: str) -> RequestTopic | None:
        tokens = model_text(self._normalizer, text)
        if not tokens:
            return None
        features = hstack([self._word.transform([tokens]), self._char.transform([tokens])]).tocsr()
        if features.nnz == 0:
            return None
        probabilities = _softmax(np.asarray(features @ self._coef.T).ravel() + self._intercept)

        best = int(probabilities.argmax())
        if probabilities[best] >= self._intent_threshold:
            return self._topic(self._classes[best])
        by_category = np.bincount(
            self._category_index, weights=probabilities, minlength=len(self._category_names)
        )
        category = int(by_category.argmax())
        if by_category[category] >= self._category_threshold:
            name = self._category_names[category]
            return RequestTopic(name, self._category_titles[name], None, None, None)
        return None

    def _topic(self, intent: str) -> RequestTopic:
        info = self._intents[intent]
        category = info["category"]
        return RequestTopic(
            category,
            self._category_titles[category],
            intent,
            info["title"],
            info["answer"],
        )


def _fitted(factory, terms: np.ndarray, idf: np.ndarray):
    vectorizer = factory({str(term): index for index, term in enumerate(terms)})
    vectorizer.idf_ = idf
    return vectorizer


def _softmax(scores: np.ndarray) -> np.ndarray:
    scores = scores - scores.max()
    exp = np.exp(scores)
    return exp / exp.sum()
