"""
JWT Authentication for Robot Assistant API
Implements secure token-based authentication
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import logging

logger = logging.getLogger(__name__)

# Security configuration
SECRET_KEY = "CHANGE_THIS_IN_PRODUCTION_USE_ENV_VARIABLE"  # Should be from environment
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class JWTAuthenticator:
    """JWT-based authentication"""

    def __init__(
        self,
        secret_key: str = SECRET_KEY,
        algorithm: str = ALGORITHM,
        token_expire_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES,
    ):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.token_expire_minutes = token_expire_minutes

    def create_access_token(
        self,
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create JWT access token

        Args:
            data: Payload data to encode
            expires_delta: Optional custom expiration time

        Returns:
            Encoded JWT token
        """
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.token_expire_minutes)

        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

        return encoded_jwt

    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Verify and decode JWT token

        Args:
            token: JWT token to verify

        Returns:
            Decoded payload

        Raises:
            HTTPException if token is invalid
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError as e:
            logger.error(f"JWT verification failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password"""
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return pwd_context.verify(plain_password, hashed_password)


# Global authenticator instance
_authenticator = JWTAuthenticator()


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Convenience function to create access token"""
    return _authenticator.create_access_token(data, expires_delta)


def verify_token(token: str) -> Dict[str, Any]:
    """Convenience function to verify token"""
    return _authenticator.verify_token(token)


async def get_current_user(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    """
    Dependency to get current authenticated user from token

    Args:
        token: JWT token from request

    Returns:
        User data from token payload
    """
    payload = verify_token(token)
    username = payload.get("sub")

    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )

    return {
        "username": username,
        **payload
    }


# Example usage with FastAPI
"""
from fastapi import APIRouter, Depends
from api.security.jwt_auth import get_current_user

router = APIRouter()

@router.get("/protected-endpoint")
async def protected_route(current_user: Dict = Depends(get_current_user)):
    return {"message": f"Hello {current_user['username']}"}
"""


if __name__ == "__main__":
    # Test JWT authentication
    auth = JWTAuthenticator()

    # Create token
    token = auth.create_access_token({"sub": "robot_user", "role": "admin"})
    print(f"Generated token: {token[:50]}...")

    # Verify token
    try:
        payload = auth.verify_token(token)
        print(f"Token verified: {payload}")
    except HTTPException as e:
        print(f"Verification failed: {e.detail}")

    # Test password hashing
    password = "secure_robot_password"
    hashed = auth.hash_password(password)
    print(f"\nPassword hash: {hashed[:50]}...")

    is_valid = auth.verify_password(password, hashed)
    print(f"Password verification: {is_valid}")
