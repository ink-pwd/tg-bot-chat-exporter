from cryptography.fernet import Fernet, InvalidToken, MultiFernet


class SessionDecryptionError(Exception):
    """Сессию не удалось расшифровать: ключ сменился или данные повреждены."""


class SessionCipher:
    """Шифрование сессий Fernet.

    Ключей может быть несколько (через запятую в SESSION_ENCRYPTION_KEY):
    шифруется первым, расшифровывается любым — так ключ можно сменить,
    не теряя уже сохранённые сессии.
    """

    def __init__(self, keys: tuple[str, ...]) -> None:
        if not keys:
            raise ValueError("at least one encryption key is required")
        self._fernet = MultiFernet([Fernet(key) for key in keys])

    def encrypt(self, plaintext: str) -> bytes:
        return self._fernet.encrypt(plaintext.encode())

    def decrypt(self, token: bytes) -> str:
        try:
            return self._fernet.decrypt(token).decode()
        except InvalidToken:
            raise SessionDecryptionError() from None

    @staticmethod
    def generate_key() -> str:
        return Fernet.generate_key().decode()
