from fastapi import APIRouter, HTTPException, status, Depends, Body, UploadFile, File
from sqlmodel import select, Session
from database.models import User, Organizations, Inventory
from database.setup import get_session
from accounts.auth.token import  get_current_user
from sqlmodel.ext.asyncio.session import AsyncSession
import pandas as pd
import io
from database.schema import InventoryInput
import uuid
from uuid import UUID
from datetime import datetime
from sqlmodel import insert
import logging
from typing import Optional
from feat.xlx_processing import file_processor
router = APIRouter()

#logger = logging.getLogger(__name__)


@router.post('/bulk_save_products')
async def add_products(
    is_manual : bool, 
    file : UploadFile = File(...), 
    session : AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user)
    ):

    get_user = await session.exec(select(User).where(User.email == current_user.sub))
    get_user = await get_user.first()

    inventory_items = await file_processor(file, clean_headers=True)

    items_barcode = [str(item["p_barcode"]) for item in inventory_items]
    catalogue_query = await session.exec(select(ProductCatalogue).where(ProductCatalogue.sku_or_barcode.in_(items_barcode)))
    catalogue_items = await catalogue_query.all()
    barcode_to_id_map = {item.sku_or_barcode: item.id for item in catalogue_items}

    items_location = [str(item["floor_no"]) for item in inventory_items]
    location_query = await session.exec(select(Inventory).where(Inventory.floor_no.in_(items_location)))
    location_items = await location_query.all()
    location_to_id_map = {item.floor_no: item.id for item in location_items}


    bulk_entry = [Inventory(
        **{
            **item,
            "org_id": current_user.org_id,
            "catalogue_id": uuid.UUID(barcode_to_id_map.get(str(item["p_barcode"]))),
            "entry_date": datetime.strptime(item["entry_date"], "%Y-%m-%d %H:%M:%S")
            if isinstance(item["entry_date"], str) else item["entry_date"],

            "p_name": str(item["p_name"]),
            "p_mg": int(item["p_mg"]),
            "p_quantity": int(item["p_quantity"]),

            "mfct_date": datetime.strptime(item["mfct_date"], "%Y-%m-%d")
            if isinstance(item["mfct_date"], str) else item["mfct_date"],

            "exp_date": datetime.strptime(item["exp_date"], "%Y-%m-%d")
            if isinstance(item["exp_date"], str) else item["exp_date"],

            "location_id": uuid.UUID(location_to_id_map.get(str(item["floor_no"]))),
            "batch_num": str(item["batch_num"]),
            "entries_by": get_user.id,
            "min_stock_lvl": int(item["min_stock_lvl"]),
            "reorder_point": int(item["reorder_point"])
            }
    ) for item in inventory_items]

    session.add_all(bulk_entry)



    await session.commit()

    return {"message": f"Successfully added products inventory items."}



@router.post('/scan_products')
async def add_products(
    data : InventoryInput,
    session : AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user)
    ):

    get_user = await session.exec(select(User).where(User.email == current_user.sub))
    get_user = await get_user.first()


    cat_id = await session.exec(select(ProductCatalogue).where(ProductCatalogue.sku_or_barcode == data.sku_or_barcode))
    cat_id = await cat_id.first()

    loc_id = await session.exec(select(Inventory).where(Inventory.floor_no == data.floor_no))
    loc_id = await loc_id.first()

    inventory_objects =  Inventory(
        org_id = current_user.org_id,
        catalogue_id = cat_id.id,
        entry_date = datetime.now(),
        entries_by = get_user.id,
        p_name = data.p_name,
        p_mg = data.p_mg,
        p_quantity = data.p_quantity,
        mfct_date = data.mfct_date,
        exp_date = data.exp_date,
        location_id = loc_id.id,
        batch_num = data.batch_num,
        min_stock_lvl = data.min_stock_lvl,
        reorder_point = data.reorder_point
    )
    session.add(inventory_objects)
    await session.commit()

    return {"message": f"Successfully added products inventory items."}