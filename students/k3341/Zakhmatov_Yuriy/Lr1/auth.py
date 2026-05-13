import os
import bcrypt
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from dotenv import load_dotenv
from sqlmodel import Session, select
from connection import get_session
from models import User

load_dotenv()

# Конфигурация JWT
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

bearer_scheme = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, hash_password: str) -> bool:
    """Проверяет обычный пароль против хэшированного пароля."""
    # Обработка PostgreSQL hex формата (начинается с \x)
    if hash_password.startswith('\\x'):
        # Конвертируем hex строку в байты
        import binascii
        hex_str = hash_password[2:]  # Убираем префикс \x
        try:
            hashed_bytes = binascii.unhexlify(hex_str)
        except (binascii.Error, ValueError):
            # Если конвертация не удалась, обрабатываем как обычную строку
            hashed_bytes = hash_password.encode('utf-8')
    else:
        # Обычная строка (UTF-8)
        hashed_bytes = hash_password.encode('utf-8')

    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_bytes)


def get_password_hash(password: str) -> str:
    """Хэширует пароль."""
    hashed_bytes = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    import binascii
    return '\\x' + binascii.hexlify(hashed_bytes).decode('utf-8')


def create_access_token(user: User, expires_delta: Optional[timedelta] = None) -> str:
    """Создает JWT токен доступа."""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "sub": str(user.id),
        "exp": expire
    }
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """Проверяет и декодирует JWT токен."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def authenticate_user(session: Session, username: str, password: str) -> Optional[User]:
    """Аутентифицирует пользователя по имени пользователя и паролю."""
    statement = select(User).where(User.username == username)
    user = session.exec(statement).first()
    if not user:
        return None
    if not verify_password(password, user.hash_password):
        return None
    return user


async def get_current_user(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
        session: Session = Depends(get_session)
) -> User:
    """Получает текущего пользователя из JWT токена."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось подтвердить учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise credentials_exception

    token = credentials.credentials
    payload = verify_token(token)
    if payload is None:
        raise credentials_exception
    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        raise credentials_exception

    user = session.get(User, user_id)
    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Получает текущего активного пользователя."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Неактивный пользователь")
    return current_user


async def get_current_superuser(current_user: User = Depends(get_current_user)) -> User:
    """Получает текущего суперпользователя."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав"
        )
    return current_user


def check_owner_or_admin(
        current_user: User,
        resource_user_id: Optional[int] = None
) -> bool:
    """
    Проверяет, имеет ли пользователь доступ к ресурсу
    Админ может все
    Обычный юзер может работать только со своими ресурсами
    """
    if current_user.is_superuser:
        return True

    if resource_user_id is None:
        return False

    return current_user.id == resource_user_id


def get_current_user_id(current_user: User = Depends(get_current_active_user)) -> int:
    """
    Возвращает ID текущего юзера
    """
    return current_user.id