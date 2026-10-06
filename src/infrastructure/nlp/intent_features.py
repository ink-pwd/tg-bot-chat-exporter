"""Признаки запроса для модели типов — одни и те же при обучении и в работе бота.

Модель обучается на леммах и понятиях из TextNormalizer, поэтому после правок
concepts.toml, stopwords.txt или fillers.txt её нужно переобучить:
python scripts/train_intent_model.py --report "<отчёт поддержки>.html"
"""
from sklearn.feature_extraction.text import TfidfVectorizer

from infrastructure.nlp.text_normalizer import TextNormalizer


def model_text(normalizer: TextNormalizer, text: str) -> str:
    return " ".join(normalizer.normalize(text).tokens)


def word_terms(text: str) -> list[str]:
    """Леммы, понятия и соседние пары: «синхронизация меню» отличается от «меню» и «синхронизации»."""
    tokens = text.split()
    return tokens + [f"{a} {b}" for a, b in zip(tokens, tokens[1:])]


def word_vectorizer(vocabulary: dict[str, int] | None = None) -> TfidfVectorizer:
    return TfidfVectorizer(analyzer=word_terms, sublinear_tf=True, min_df=2, vocabulary=vocabulary)


def char_vectorizer(vocabulary: dict[str, int] | None = None) -> TfidfVectorizer:
    """Кусочки слов по 3–5 букв: формы слов, опечатки, ru/uk-варианты одного слова."""
    return TfidfVectorizer(
        analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, min_df=3, vocabulary=vocabulary
    )
