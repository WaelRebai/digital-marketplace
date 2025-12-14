from datetime import datetime, timedelta
from typing import Optional, Generic, TypeVar, Any
from fastapi import HTTPException, status, Header, Depends
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext
from pydantic import BaseModel
from pydantic_settings import BaseSettings
from jose import JWTError, jwt
import uuid

# --- Configuration ---
class Settings(BaseSettings):
    MONGO_URL: str = "mongodb://mongodb:27017"
    SECRET_KEY: str = "secret"
    REFRESH_SECRET_KEY: str = "refresh_secret"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    class Config:
        env_file = ".env"

settings = Settings()

# --- Database ---
def get_db_client(url: str = settings.MONGO_URL) -> AsyncIOMotorClient:
    return AsyncIOMotorClient(url)

# --- Authentication ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Add JTI
    if "jti" not in to_encode:
        to_encode.update({"jti": str(uuid.uuid4())})

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    if "jti" not in to_encode:
        to_encode.update({"jti": str(uuid.uuid4())})
        
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.REFRESH_SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

# --- Response Models ---
T = TypeVar("T")

class SuccessResponse(BaseModel, Generic[T]):
    success: bool = True
    data: Optional[T] = None
    message: Optional[str] = None

class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    details: Optional[Any] = None

class HealthResponse(BaseModel):
    service: str
    status: str
    timestamp: datetime
    version: str
    database: Optional[str] = None
    dependencies: Optional[dict] = None


# --- Exceptions ---
class AppException(HTTPException):
    def __init__(
        self,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        detail: str = "An error occurred",
        headers: Optional[dict] = None
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)

class NotFoundException(AppException):
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

class UnauthorizedException(AppException):
    def __init__(self, detail: str = "Unauthorized"):
         super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )

# --- Decorators/Dependencies ---
async def require_auth(authorization: str = Header(...)) -> dict:
    scheme, _, param = authorization.partition(" ")
    if not authorization or scheme.lower() != "bearer":
         raise UnauthorizedException(detail="Invalid authentication credentials")
    return verify_token(param)
