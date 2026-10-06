from dataclasses import dataclass


@dataclass(frozen=True)
class RequestTopic:
    """К чему относится запрос клиента по классификации поддержки.

    Тип (intent) известен не всегда: иногда понятна только категория.
    """

    category: str  # ключ категории: menu, orders, …
    category_title: str
    intent: str | None  # ключ типа: menu_stop_list, …
    intent_title: str | None
    answer: str | None  # стандартный ответ поддержки на такой запрос
