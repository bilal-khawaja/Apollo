import os
from datetime import datetime, timedelta
from jose import jwt
from typing import Optional
from decouple import config
from typing import Dict
from passlib.context import CryptContext
import uuid
from uuid import UUID

SECRET: str = config("SECRET_KEY", cast=str)
ALGORITHM: str = config("ALGORITHM", cast=str ,default="HS256")
expiretime: int = config("ACCESS_TOKEN_EXPIRE_MINUTES", cast=int, default=30)

def create_access_token(user_email:str, role:str, org_id:uuid.UUID, expiretime:int) -> str:
    expire_at = datetime.utcnow() + timedelta(minutes=expiretime)
    payload = {
        "sub": user_email,
        "role":role,
        "org_id": str(org_id),
        "exp": int(expire_at.timestamp())
        }
    token = jwt.encode(payload, SECRET, algorithm=ALGORITHM)
    
    return token

def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
        
        if payload and "sub" in payload:
            payload["user_id"] = payload["sub"]     
        return payload
    except jwt.ExpiredSignatureError:
        print("DEBUG: Token has expired")
        return None
    except jwt.JWTError as e:
        print(f"DEBUG: JWT Error details: {str(e)}") 
        return None
    except Exception as e:
        print(f"DEBUG: Unknown Error: {str(e)}")
        return None