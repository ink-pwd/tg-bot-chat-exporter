"""Приведение запроса к набору понятий: «Як змінити картку?» → ["change", "card"]."""
import difflib
import re
import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from infrastructure.nlp.lemmatizer import Lemmatizer, looks_ukrainian

RESOURCES = Path(__file__).parent / "resources"

_URL = re.compile(r"https?://\S+|www\.\S+|\S+@\S+\.\S+|@\w+")
_NUMBER = re.compile(r"\d+")
_APOSTROPHES = re.compile(r"[’ʼ`´]")
_WORD = re.compile(r"[a-zа-яёіїєґ']+(?:-[a-zа-яёіїєґ']+)*")
# однокоренные слова ru/uk вне словаря понятий сводятся к общему написанию:
# «історія» и «история» → «история», «кабінет» и «кабинет» → «кабинет»
_COGNATE_FOLD = str.maketrans({"і": "и", "ї": "и", "є": "е", "ґ": "г", "ы": "и", "'": ""})
NUMBER_TOKEN = "<num>"
CONCEPT_PREFIX = "#"


@dataclass(frozen=True)
class NormalizedText:
    tokens: list[str]  # понятия (#change) и леммы без стоп-слов
    had_typos: bool = False  # были исправлены опечатки

    @property
    def key(self) -> str:
        """Смысл без учёта порядка и повторов: одинаковый у «изменить оплату» и «оплату изменить»."""
        return " ".join(sorted(set(self.tokens)))


class TextNormalizer:
    def __init__(
        self,
        lemmatizer: Lemmatizer,
        fillers: list[str],
        stopwords: set[str],
        concepts: dict[str, set[str]],
    ) -> None:
        self._lemmatizer = lemmatizer
        self._stopwords = stopwords
        self._concept_of = {word: name for name, words in concepts.items() for word in words}
        self._concept_words = sorted(self._concept_of)
        self._correct_typo = lru_cache(maxsize=20_000)(self._closest_concept_word)
        # длинные фразы первыми, чтобы «подскажите пожалуйста» не порезалось на части
        phrases = sorted(fillers, key=len, reverse=True)
        self._fillers = re.compile(
            r"(?<![\wіїєґ'])(?:" + "|".join(map(re.escape, phrases)) + r")(?![\wіїєґ'])"
        )

    @classmethod
    def from_resources(cls, lemmatizer: Lemmatizer, directory: Path = RESOURCES) -> "TextNormalizer":
        concepts_file = tomllib.loads((directory / "concepts.toml").read_text(encoding="utf-8"))
        return cls(
            lemmatizer,
            fillers=_read_lines(directory / "fillers.txt"),
            stopwords=set(_read_lines(directory / "stopwords.txt")),
            concepts={name: set(c["words"]) for name, c in concepts_file.items()},
        )

    def normalize(self, text: str) -> NormalizedText:
        text = text.lower().replace("ё", "е")
        text = _APOSTROPHES.sub("'", text)
        text = _URL.sub(" ", text)
        text = _NUMBER.sub(f" {NUMBER_TOKEN} ", text)
        prefer_ukrainian = looks_ukrainian(" ".join(_WORD.findall(text)))
        text = self._fillers.sub(" ", text)

        tokens = []
        had_typos = False
        for raw in text.split():
            if raw == NUMBER_TOKEN:
                tokens.append(raw)
                continue
            for word in _WORD.findall(raw):
                word = word.strip("'")
                lemma = self._lemmatizer.lemma(word, prefer_ukrainian).replace("ё", "е")
                if lemma in self._stopwords or word in self._stopwords:
                    continue
                concept = self._concept_of.get(lemma) or self._concept_of.get(word)
                if concept is None and not self._lemmatizer.is_known(word):
                    concept = self._concept_of.get(self._correct_typo(word))
                    had_typos = had_typos or concept is not None
                if concept:
                    tokens.append(CONCEPT_PREFIX + concept)
                elif len(lemma) > 2:
                    tokens.append(lemma.translate(_COGNATE_FOLD))
        return NormalizedText(tokens, had_typos)

    def _closest_concept_word(self, word: str) -> str | None:
        """Опечатка в слове из словаря понятий: «спосб» → «способ», «оплаті» → «оплата»."""
        if len(word) < 4:
            return None
        matches = difflib.get_close_matches(word, self._concept_words, n=1, cutoff=0.8)
        return matches[0] if matches else None


def load_concept_labels(directory: Path = RESOURCES) -> dict[str, str]:
    concepts = tomllib.loads((directory / "concepts.toml").read_text(encoding="utf-8"))
    return {name: concept.get("label", name) for name, concept in concepts.items()}


def _read_lines(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]
