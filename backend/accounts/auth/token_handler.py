import os
from datetime import datetime, timedelta
from jose import jwt
from typing import Optional
from decouple import config
from typing import Dict
from passlib.context import CryptContext
SECRET: str = config("SECRET_KEY", cast=str)
ALGORITHM: str = config("ALGORITHM", cast=str ,default="HS256")

def create_access_token(user_id:int, role:str, expiretime:int) -> Dict[str,str]:
    payload = {
        "sub": str(user_id),
        "role":role,
        "exp": datetime.utcnow() + timedelta(minutes=expiretime)
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