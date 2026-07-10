from fastapi import APIRouter, HTTPException, status, Depends, Body
from sqlmodel import select, Session
from database.models import User, Organizations, ProductCatalogue, Locations
from database.setup import get_session
from ..auth.token import get_current_user
from ..auth.token_handler import create_access_token
from sqlmodel.ext.asyncio.session import AsyncSession
from dotenv import load_dotenv
import os
import uuid
from uuid import UUID
from fastapi import UploadFile, File
from feat.xlx_processing_generation import file_processor
from database.schema import UpdateCatalogue, UpdateStorageInfo
from typing import Optional, List

router = APIRouter()

@router.post('/setup_storage_rooms')
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


@router.post('/upload_product_catalogue')
async def upload_catalogue(
    file : UploadFile = File(...), 
    session : AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user)
):

    catalogue_items_dict = await file_processor(file, clean_headers=True)
    catalogue_ojects = [ProductCatalogue(
        **{
            **item,
            "org_id": current_user.org_id,
            "sku_or_barcode": str(item["sku_or_barcode"]),
            "strength": str(item["strength"])
        }
    ) for item in catalogue_items_dict]

    session.add_all(catalogue_ojects)
    
    await session.commit()
    return {"message": f"Successfully uploaded {len(catalogue_ojects)} products."}


@router.put('/update_product_catalogue')
async def update_catalogue(
    data : UpdateCatalogue,
    id : Optional[UUID] = None,
    session : AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user),
):

    try:
        if not id:

            add_info = ProductCatalogue(
                org_id = current_user.org_id,
                p_name = data.p_name,
                strength = data.strength,
                sku_or_barcode = data.sku_or_barcode,
                unit_type = data.unit_type,
                manufacturer = data.manufacturer
            )

            session.add(add_info)

        else:
            update_info = await session.exec(select(ProductCatalogue).where(ProductCatalogue.id == id))
            update_info = await update_info.first()

            if not update_info:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                 detail="Product not found in your catalogue.")
            
            fields_to_update = data.model_dump(exclude_unset=True)

            for key, value in fields_to_update.items():
                setattr(update_info, key, value)
    
        await session.commit()
        return {"message": "Product catalogue updated successfully."}

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"An error occurred while updating the product catalogue: {str(e)}")


@router.put('/update_storage_info')
async def update_storage_info(
    data : UpdateStorageInfo,
    id : Optional[UUID] = None,
    session : AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user),
):

    try:
        if not id:

            add_info = Locations(
                org_id = current_user.org_id,
                floor_no = data.floor_no,
                ward_no = data.ward_no,
                shelf_no = data.shelf_no,
                bin_id = data.bin_id
            )

            session.add(add_info)

        else:
            update_info = await session.exec(select(Locations).where(Locations.id == id))
            update_info = await update_info.first()

            if not update_info:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                 detail="Storage unit not found in your locations.")
            
            fields_to_update = data.model_dump(exclude_unset=True)

            for key, value in fields_to_update.items():
                setattr(update_info, key, value)
    
        await session.commit()
        return {"message": "Storage information updated successfully."}

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"An error occurred while updating the storage information: {str(e)}")