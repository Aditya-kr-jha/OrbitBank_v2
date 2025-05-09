import logging
from datetime import timedelta, datetime, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status, Query, WebSocketException
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError, ExpiredSignatureError, PyJWTError
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Session, select

from app.config import settings
from app.db.session import get_async_session
from app.models.models import User, get_user_async
from app.schemas.token import TokenData

logger = logging.getLogger(__name__)

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme for token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# Function to hash a password
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


# Function to verify a password
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


async def authenticate_user(username: str, password: str, session) -> User | bool:
    user = await get_user_async(username, session)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def create_access_token(data: dict, expires_delta: int | timedelta = None) -> str:
    """
    Create an access token with the given data and expiration time.

    Args:
        data (dict): The data to include in the token.
        expires_delta (int or timedelta, optional): The expiration time in seconds or as a timedelta. Defaults to None.

    Returns:
        str: The generated access token.
    """
    to_encode = data.copy()
    if expires_delta:
        if isinstance(expires_delta, timedelta):
            expires = datetime.now(timezone.utc) + expires_delta
        else:
            expires = datetime.now(timezone.utc) + timedelta(seconds=expires_delta)
    else:
        expires = datetime.now(timezone.utc) + timedelta(minutes=150)
    to_encode.update({"exp": expires})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: AsyncSession = Depends(get_async_session),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except InvalidTokenError:
        raise credentials_exception
    user = await get_user_async(token_data.username, session)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)):
    return current_user


def create_verification_token(email: str) -> str:
    """Generates a secure JWT token for email verification."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {
        "sub": email,  # Subject of the token is the email
        "exp": expire,
        "purpose": "email_verification",  # Add a purpose claim
    }
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_verification_token(token: str) -> str | None:
    """
    Verifies the email verification token.
    Returns the email if valid, None otherwise.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str | None = payload.get("sub")
        purpose: str | None = payload.get("purpose")

        if email is None:
            logger.warning("Verification token missing 'sub' (email).")
            return None
        if purpose != "email_verification":
            logger.warning(
                f"Token purpose mismatch. Expected 'email_verification', got '{purpose}'."
            )
            return None
        return email
    except ExpiredSignatureError:
        logger.warning("Email verification token has expired.")
        return None
    except InvalidTokenError as e:  # Catches various invalid token issues
        logger.warning(f"Invalid email verification token: {e}")
        return None
    except PyJWTError as e:  # Catch-all for other PyJWT errors
        logger.warning(f"PyJWTError during verification token decode: {e}")
        return None
    except Exception as e:
        logger.exception(f"Unexpected error during token verification: {e}")
        return None
