class DomainError(Exception):
    """Базовая ошибка бизнес-правил."""


class AccountNotFound(DomainError):
    """Аккаунта нет или он принадлежит другому пользователю.

    Эти случаи намеренно не различаются: чужой пользователь не должен
    узнать, что аккаунт с таким id существует.
    """


class AccountOwnedByAnotherUser(DomainError):
    """Telegram-аккаунт уже подключён другим пользователем бота."""


class InvalidPhoneNumber(DomainError):
    pass
