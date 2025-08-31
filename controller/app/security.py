from dotenv import load_dotenv
load_dotenv()
import os
import hmac
import hashlib
from cryptography.fernet import Fernet
from typing import Optional

def validate_api_key(api_key: str) -> bool:
    expected_key = os.getenv("CN_API_KEY")
    print(f"DEBUG: Validating API Key: {api_key}")
    print(f"DEBUG: Expected API Key: {expected_key}")
    if not expected_key or not api_key:
        return False
    return hmac.compare_digest(api_key, expected_key)

def get_encryption_key() -> bytes:
    key_str = os.getenv("ENCRYPTION_KEY")
    if not key_str:
        raise ValueError("Encryption key not configured")
    return hashlib.sha256(key_str.encode()).digest()

def encrypt_data(data: str) -> Optional[bytes]:
    try:
        f = Fernet(Fernet.generate_key())
        return f.encrypt(data.encode())
    except Exception:
        return None

def decrypt_data(encrypted_data: bytes) -> Optional[str]:
    try:
        f = Fernet(Fernet.generate_key())
        return f.decrypt(encrypted_data).decode()
    except Exception:
        return None