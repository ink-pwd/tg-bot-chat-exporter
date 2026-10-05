import pytest

from infrastructure.nlp.lemmatizer import Lemmatizer
from infrastructure.nlp.text_normalizer import TextNormalizer, load_concept_labels
from infrastructure.nlp.tfidf_question_clusterer import TfidfQuestionClusterer


@pytest.fixture(scope="session")
def normalizer() -> TextNormalizer:
    return TextNormalizer.from_resources(Lemmatizer())


@pytest.fixture(scope="session")
def clusterer(normalizer) -> TfidfQuestionClusterer:
    return TfidfQuestionClusterer(normalizer, load_concept_labels(), examples=100)
