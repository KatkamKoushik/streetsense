import uuid
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
import bcrypt
import jwt
from jwt.exceptions import PyJWTError, ExpiredSignatureError, InvalidTokenError
from fastapi import HTTPException, status
from app.core.config import settings


def hash_device_secret(secret: str) -> str:
    """Hash a device secret/verifier using bcrypt."""
    return bcrypt.hashpw(secret.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_device_secret(secret: str, hashed_verifier: Optional[str]) -> bool:
    """Verify a plain secret against a stored bcrypt verifier."""
    if not secret or not hashed_verifier:
        return False
    try:
        return bcrypt.checkpw(secret.encode("utf-8"), hashed_verifier.encode("utf-8"))
    except Exception:
        return False


def generate_secure_device_secret() -> str:
    """Generate a high-entropy, 256-bit cryptographic device credential."""
    return f"sec_{secrets.token_hex(32)}"


def create_device_token(
    device_id: str,
    scopes: Optional[List[str]] = None,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Issue a signed JWT bound strictly to an active device identity."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    effective_scopes = scopes or ["device:telemetry"]

    payload: Dict[str, Any] = {
        "sub": device_id,
        "device_id": device_id,
        "role": "device",
        "scopes": effective_scopes,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE_DEVICE,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": str(uuid.uuid4())
    }

    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_console_token(
    client_id: str = "web_console_operator",
    scopes: Optional[List[str]] = None,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Issue a signed JWT for an authorized web console / operator."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.CONSOLE_TOKEN_EXPIRE_MINUTES)

    effective_scopes = scopes or ["console:observe"]

    payload: Dict[str, Any] = {
        "sub": client_id,
        "role": "observer",
        "scopes": effective_scopes,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE_CONSOLE,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": str(uuid.uuid4())
    }

    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_and_verify_token(
    token: str,
    expected_audience: str,
    required_scope: Optional[str] = None
) -> Dict[str, Any]:
    """
    Cryptographically verify a token's signature, algorithm, issuer, audience, and scope.
    Fails closed on any discrepancy.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is missing",
            headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            issuer=settings.JWT_ISSUER,
            audience=expected_audience
        )
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\", error_description=\"token has expired\""}
        )
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""}
        )
    except PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token verification failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if required_scope:
        token_scopes = payload.get("scopes", [])
        if required_scope not in token_scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient authorization scope. Required: '{required_scope}'",
                headers={"WWW-Authenticate": f"Bearer error=\"insufficient_scope\", scope=\"{required_scope}\""}
            )

    return payload


def redact_location(lat: Optional[float], lon: Optional[float]) -> str:
    """Mask fine-grained location in log statements to preserve pedestrian privacy."""
    if lat is None or lon is None:
        return "lat=None, lon=None"
    try:
        coarse_lat = f"{lat:.2f}***"
        coarse_lon = f"{lon:.2f}***"
        return f"lat={coarse_lat}, lon={coarse_lon}"
    except Exception:
        return "lat=***, lon=***"
