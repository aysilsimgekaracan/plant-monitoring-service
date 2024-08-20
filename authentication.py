from fastapi import Depends, HTTPException, APIRouter
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext
from pydantic import BaseModel
import motor.motor_asyncio
import os
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

MONGODB_URL = os.getenv("MONGODB_URL")

client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URL)
db = client.askdb

########################################################################
# MARK: MODELS
########################################################################

class UserCredentials(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    
########################################################################
# MARK: AUTH
########################################################################

SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours

# Initialize a password context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme for token generation
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Function to create an access token
def create_access_token(data: dict, expires_delta_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=expires_delta_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Function to get the current user from the token
async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        user = await db["api_users"].find_one({"username": username})
        if user is None:
            raise credentials_exception
        return user
    except JWTError:
        raise credentials_exception

# FastAPI route to get a token
@router.post("/GetAuth", tags=["Authentication"])
async def login_for_access_token(token_request: UserCredentials):
    username = token_request.username
    password = token_request.password

    # Authenticate the user by checking their credentials in MongoDB
    user = await db["api_users"].find_one({"username": username})

    if user is None or not pwd_context.verify(password, user["password"]):
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    # Check if a token already exists and is still valid
    existing_token = user.get("token")
    if existing_token:
        try:
            payload = jwt.decode(existing_token, SECRET_KEY, algorithms=[ALGORITHM])
            # If token is still valid, return it
            if payload["exp"] > datetime.utcnow().timestamp():
                return {"access_token": existing_token, "token_type": "bearer"}
        except JWTError:
            pass  # If there's an error, we'll generate a new token below

    # If no valid token exists, generate a new one
    access_token = create_access_token({"sub": user["username"]})
    # Store the new token in MongoDB
    await db["api_users"].update_one({"username": username}, {"$set": {"token": access_token}})
    return {"access_token": access_token, "token_type": "bearer"}
