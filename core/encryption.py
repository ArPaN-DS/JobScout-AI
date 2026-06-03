import os
import logging
from django.conf import settings
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

# A default development key for convenience. Change this in production!
DEFAULT_DEV_KEY = Fernet.generate_key().decode('utf-8')

_fernet_instance = None

def get_fernet() -> Fernet:
    global _fernet_instance
    if _fernet_instance is not None:
        return _fernet_instance

    key = os.getenv("FIELD_ENCRYPTION_KEY")
    
    if not key:
        import sys
        is_testing = 'test' in sys.argv or 'test_coverage' in sys.argv or getattr(settings, 'TESTING', False)
        if settings.DEBUG or is_testing:
            logger.warning(
                "FIELD_ENCRYPTION_KEY environment variable is not set. "
                "Using a transient key for development/testing."
            )
            key = DEFAULT_DEV_KEY
        else:
            raise RuntimeError(
                "FIELD_ENCRYPTION_KEY must be set in production to encrypt/decrypt database secrets."
            )
            
    try:
        # Convert string to bytes if needed and initialize Fernet
        key_bytes = key.encode('utf-8') if isinstance(key, str) else key
        _fernet_instance = Fernet(key_bytes)
    except Exception as exc:
        logger.error(f"Failed to initialize Fernet encryption: {exc}")
        if settings.DEBUG:
            # Fallback to dev key to prevent complete app crash in local dev
            _fernet_instance = Fernet(DEFAULT_DEV_KEY.encode('utf-8'))
        else:
            raise RuntimeError(f"Invalid FIELD_ENCRYPTION_KEY provided: {exc}") from exc

    return _fernet_instance

def encrypt_value(plain_text: str) -> str:
    """Encrypts a string and returns a web-safe base64 string."""
    if not plain_text:
        return ""
    f = get_fernet()
    return f.encrypt(plain_text.encode('utf-8')).decode('utf-8')

def decrypt_value(cipher_text: str) -> str:
    """Decrypts a base64 cipher text and returns the decrypted plain text."""
    if not cipher_text:
        return ""
    f = get_fernet()
    try:
        return f.decrypt(cipher_text.encode('utf-8')).decode('utf-8')
    except Exception as exc:
        logger.error(f"Failed to decrypt value: {exc}")
        raise ValueError("Decryption failed. The secret key might be invalid or the payload is corrupted.") from exc
