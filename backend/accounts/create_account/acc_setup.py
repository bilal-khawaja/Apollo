from fastapi import APIRouter, HTTPException, status, Depends, Body
from sqlmodel import select, Session
from database.models import User, Organizations
from database.setup import get_session
from database.schema import 
from ..auth.token import get_current_user
from ..auth.token_handler import create_access_token
from sqlmodel.ext.asyncio.session import AsyncSession
from dotenv import load_dotenv
import os
import uuid
from uuid import UUID


router = APIRouter()

# @router.put('/setup_storage_rooms')
# async def storage_units(
#     data : List[LocationInput] = ,
# )