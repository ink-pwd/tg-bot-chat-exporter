import pytest

from infrastructure.security.session_cipher import SessionCipher, SessionDecryptionError


def test_roundtrip():
    cipher = SessionCipher((SessionCipher.generate_key(),))

    token = cipher.encrypt("session-string")

    assert b"session-string" not in token
    assert cipher.decrypt(token) == "session-string"


def test_key_rotation_keeps_old_sessions_readable():
    old_key, new_key = SessionCipher.generate_key(), SessionCipher.generate_key()
    old_token = SessionCipher((old_key,)).encrypt("old")

    rotated = SessionCipher((new_key, old_key))

    assert rotated.decrypt(old_token) == "old"
    assert SessionCipher((new_key,)).decrypt(rotated.encrypt("new")) == "new"


def test_wrong_key_raises():
    token = SessionCipher((SessionCipher.generate_key(),)).encrypt("s")

    with pytest.raises(SessionDecryptionError):
        SessionCipher((SessionCipher.generate_key(),)).decrypt(token)
