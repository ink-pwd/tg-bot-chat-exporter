"""Начальная форма слова для русского и украинского (pymorphy3) с определением языка слова."""
from functools import lru_cache

import pymorphy3

_UKRAINIAN_ONLY = set("іїєґ")
_RUSSIAN_ONLY = set("ыэъё")
# частые украинские слова без «і/ї/є» — по ним узнаём язык сообщения
_UKRAINIAN_MARKERS = {
    "як", "де", "чи", "що", "коли", "чому", "можна", "треба", "потрібно", "будь", "ласка",
    "мені", "мене", "ваш", "кошти", "гроші", "зараз", "вже", "ще", "тому", "дуже", "добрий",
}


class Lemmatizer:
    """Начальная форма слова для украинского и русского.

    Язык слова определяется по буквам (і, ї, є, ґ — украинский; ы, э, ъ — русский),
    а для общих слов — по языку всего сообщения и по тому, какой словарь слово знает.
    """

    def __init__(self) -> None:
        self._ru = pymorphy3.MorphAnalyzer(lang="ru")
        self._uk = pymorphy3.MorphAnalyzer(lang="uk")
        self.lemma = lru_cache(maxsize=50_000)(self._lemma)

    def _lemma(self, word: str, prefer_ukrainian: bool) -> str:
        letters = set(word)
        if letters & _UKRAINIAN_ONLY:
            return self._normal_form(self._uk, word)
        if letters & _RUSSIAN_ONLY:
            return self._normal_form(self._ru, word)
        first, second = (self._uk, self._ru) if prefer_ukrainian else (self._ru, self._uk)
        if first.word_is_known(word) or not second.word_is_known(word):
            return self._normal_form(first, word)
        return self._normal_form(second, word)

    def is_known(self, word: str) -> bool:
        """Слово есть хотя бы в одном словаре — значит, это не опечатка."""
        return self._ru.word_is_known(word) or self._uk.word_is_known(word)

    @staticmethod
    def _normal_form(analyzer: pymorphy3.MorphAnalyzer, word: str) -> str:
        return analyzer.parse(word)[0].normal_form


def looks_ukrainian(text: str) -> bool:
    """Украинские буквы или характерные украинские слова в сообщении."""
    if set(text) & _UKRAINIAN_ONLY:
        return True
    return any(word in _UKRAINIAN_MARKERS for word in text.split())
