from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status


class AuthService:
    def __init__(self, secret_key: str) -> None:
        self.secret_key = secret_key or "hospital-web-dev-secret"

    def hash_password(self, password: str) -> str:
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000)
        return f"{salt}${digest.hex()}"

    def verify_password(self, password: str, password_hash: str) -> bool:
        try:
            salt, expected = password_hash.split("$", 1)
        except ValueError:
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000).hex()
        return hmac.compare_digest(digest, expected)

    def create_token(self, user_id: int, username: str, role: str = "admin", expires_hours: int = 12) -> str:
        payload = {
            "sub": user_id,
            "username": username,
            "role": role,
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=expires_hours)).timestamp()),
        }
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        signature = hmac.new(self.secret_key.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{body}.{signature}"

    def decode_token(self, token: str) -> dict[str, Any]:
        try:
            body, signature = token.rsplit(".", 1)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效令牌") from exc
        expected = hmac.new(self.secret_key.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效令牌")
        payload = json.loads(body)
        if int(payload.get("exp", 0)) < int(datetime.now(timezone.utc).timestamp()):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已过期")
        return payload
