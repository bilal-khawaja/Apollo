from fastapi import APIRouter, HTTPException, status, Depends, Body
from sqlmodel import select, Session
from database.models import User, Organizations
from database.setup import get_session
from ..auth.token import get_current_user
from ..auth.token_handler import create_access_token
from sqlmodel.ext.asyncio.session import AsyncSession
from dotenv import load_dotenv
import os
import uuid
from uuid import UUID
from fastapi import UploadFile, File
from feat.xlx_processing import file_processor
from database.models import Locations


router = APIRouter()

@router.put('/setup_storage_rooms')
async def storage_units(
    data : UploadFile = File(...),
    current_user : User = Depends(get_current_user),
    session : AsyncSession = Depends(get_session)
 ):

    fetched_locations = await file_processor(data, clean_headers=True)

    storage_unit_entry = [Locations(
        
        **{
            **item,
            "org_id": current_user.org_id,
            "floor_no": int(item["floor_no"]),
            "ward_no": str(item["ward_no"]),
            "shelf_no": str(item["shelf_no"]),
            "bin_id": str(item["bin_id"])
        }
    ) for item in fetched_locations
    ]

    session.add_all(storage_unit_entry)
    await session.commit()
    

    return {"message": f"Successfully added storage units."}