"""JWT 令牌签发与校验（对应技能：组织与权限-issue_token / verify_token）。"""
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

ALGORITHM = "HS256"

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def issue_token(user_id: int, username: str, expires_minutes: int | None = None) -> str:
    """签发 JWT 令牌。"""
    exp = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.access_token_expire_minutes
    )
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": exp,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def verify_token(token: str) -> dict:
    """校验 JWT 令牌与用户登录态，返回 payload。"""
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise ValueError(f"invalid token: {exc}") from exc


def hash_password(plain: str) -> str:
    """密码加盐哈希。"""
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """校验密码。"""
    return _pwd_ctx.verify(plain, hashed)