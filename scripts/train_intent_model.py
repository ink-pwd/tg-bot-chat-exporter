"""Обучение модели типов запросов на размеченном отчёте по поддержке.

    python scripts/train_intent_model.py --report "Dots Support Report.html"

Отчёт — HTML-файл годового анализа поддержки: в нём встроены примеры вопросов
с уже проставленным типом. Скрипт:
1. достаёт примеры из отчёта (тексты переписок дальше этого процесса не уходят);
2. меряет точность на отложенных 20% и печатает её;
3. обучается на всех примерах и сохраняет в src/infrastructure/nlp/resources/intent_model.npz
   только словари признаков и веса модели.

Сам отчёт и примеры в репозиторий не кладутся: там переписки клиентов.
"""
import argparse
import json
import random
import re
import sys
import tomllib
from pathlib import Path

import numpy as np
from scipy.sparse import hstack
from sklearn.linear_model import LogisticRegression

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from infrastructure.nlp.intent_model_classifier import MODEL_FILE, TAXONOMY_FILE  # noqa: E402
from infrastructure.nlp.intent_model_features import (  # noqa: E402
    char_vectorizer,
    model_text,
    word_vectorizer,
)
from infrastructure.nlp.ru_uk_lemmatizer import Lemmatizer  # noqa: E402
from infrastructure.nlp.text_normalizer import TextNormalizer  # noqa: E402

C = 8.0
HOLDOUT = 0.2
INTENT_THRESHOLD = 0.4
# признаки, вес которых ни в одном типе не дотягивает до этого, не влияют на ответ — выбрасываем
PRUNE_BELOW = 0.05
# в словаре слов не должно быть ничего похожего на персональные данные
_SUSPICIOUS = re.compile(r"[@\d]|^.{25,}$")


def load_examples(report: Path) -> list[tuple[str, str]]:
    html = report.read_text(encoding="utf-8")
    script = re.findall(r"<script[^>]*>(.*?)</script>", html, re.S)[0]
    data, _ = json.JSONDecoder().raw_decode(script[script.index("{", script.index("R")):])
    examples: dict[tuple[str, str], None] = {}
    for year in data["data"].values():
        faq = year["faq"]
        for group in faq["group"]:
            for example in group["examples"]:
                examples[(group["k"], example["q"])] = None
        for account in faq["accounts"]:
            for top in account.get("top", []):
                examples[(top["k"], top["q"])] = None
    # реплики в отчёте склеены через « / »
    return [(intent, text.replace(" / ", "\n")) for intent, text in examples]


def fit(texts: list[str], labels: list[str]):
    word = word_vectorizer()
    char = char_vectorizer()
    features = hstack([word.fit_transform(texts), char.fit_transform(texts)]).tocsr()
    model = LogisticRegression(max_iter=3000, C=C, class_weight="balanced").fit(features, labels)
    return word, char, model


def evaluate(texts: list[str], labels: list[str], categories: dict[str, str]) -> None:
    order = list(range(len(texts)))
    random.Random(7).shuffle(order)
    cut = int(len(order) * (1 - HOLDOUT))
    train, test = order[:cut], order[cut:]
    word, char, model = fit([texts[i] for i in train], [labels[i] for i in train])
    features = hstack(
        [word.transform([texts[i] for i in test]), char.transform([texts[i] for i in test])]
    ).tocsr()
    probabilities = model.predict_proba(features)
    predicted = model.classes_[probabilities.argmax(1)]
    confident = probabilities.max(1) >= INTENT_THRESHOLD
    truth = np.array([labels[i] for i in test])
    same_category = np.array([categories[p] == categories[t] for p, t in zip(predicted, truth)])
    print(f"Проверка на отложенных {len(test)} примерах:")
    print(f"  тип определён у {confident.mean():.0%} запросов, из них верно {(predicted == truth)[confident].mean():.0%}")
    print(f"  категория у них же верна в {same_category[confident].mean():.0%}")
    print(f"  без порога: тип верен в {(predicted == truth).mean():.0%}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--report", type=Path, required=True, help="HTML-отчёт с размеченными вопросами")
    args = parser.parse_args()

    taxonomy = tomllib.loads(TAXONOMY_FILE.read_text(encoding="utf-8"))
    categories = {key: intent["category"] for key, intent in taxonomy["intents"].items()}
    examples = [(intent, text) for intent, text in load_examples(args.report) if intent in categories]
    print(f"Примеров: {len(examples)}, типов: {len({i for i, _ in examples})}")

    normalizer = TextNormalizer.from_resources(Lemmatizer())
    pairs = [(intent, model_text(normalizer, text)) for intent, text in examples]
    pairs = [(intent, text) for intent, text in pairs if text]
    labels = [intent for intent, _ in pairs]
    texts = [text for _, text in pairs]

    evaluate(texts, labels, categories)

    word, char, model = fit(texts, labels)
    word_terms = word.get_feature_names_out()
    char_terms = char.get_feature_names_out()
    coef = model.coef_.astype(np.float32)

    keep = np.abs(coef).max(0) >= PRUNE_BELOW
    keep[: len(word_terms)] &= np.array([not _SUSPICIOUS.search(t) for t in word_terms])
    word_keep, char_keep = keep[: len(word_terms)], keep[len(word_terms):]
    np.savez_compressed(
        MODEL_FILE,
        classes=np.array(model.classes_, dtype=str),
        word_terms=np.array(word_terms[word_keep], dtype=str),
        word_idf=word.idf_[word_keep].astype(np.float32),
        char_terms=np.array(char_terms[char_keep], dtype=str),
        char_idf=char.idf_[char_keep].astype(np.float32),
        coef=coef[:, keep],
        intercept=model.intercept_.astype(np.float32),
    )
    print(
        f"Сохранено: {MODEL_FILE.relative_to(ROOT)} — признаков {keep.sum()} из {keep.size}, "
        f"{MODEL_FILE.stat().st_size / 1024 / 1024:.1f} МБ"
    )


if __name__ == "__main__":
    main()
