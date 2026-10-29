import re
from datetime import datetime, timedelta
from typing import Tuple, Dict, Any, Optional

MAX_FAILED_ATTEMPTS = 4
LOCKOUT_MINUTES = 3

def validate_password_strength(password: str) -> Tuple[bool, str]:
    """
    Validates password based on security requirements:
    - Minimum 8 characters
    - At least 1 uppercase letter
    - At least 1 number
    - At least 1 special character
    """
    if not password or len(password) < 8:
        return False, "A senha deve conter no mínimo 8 caracteres."
    if not re.search(r'[A-Z]', password):
        return False, "A senha deve conter pelo menos 1 letra maiúscula (A-Z)."
    if not re.search(r'[0-9]', password):
        return False, "A senha deve conter pelo menos 1 número (0-9)."
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?~`]', password):
        return False, "A senha deve conter pelo menos 1 caractere especial (ex: ! @ # $ % & *)."
    
    return True, "Senha válida e segura."

def check_account_lockout(user: Dict[str, Any]) -> Tuple[bool, int]:
    """
    Checks if account is currently locked due to >= 4 failed login attempts.
    Returns (is_locked, remaining_seconds).
    """
    locked_until_str = user.get("locked_until")
    if not locked_until_str:
        return False, 0

    try:
        locked_until = datetime.fromisoformat(locked_until_str)
        now = datetime.now()
        if now < locked_until:
            remaining = int((locked_until - now).total_seconds())
            return True, max(1, remaining)
    except Exception:
        pass

    return False, 0
