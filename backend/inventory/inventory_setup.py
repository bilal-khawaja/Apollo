from fastapi import APIRouter, HTTPException, status, Depends, Body, UploadFile, File
from sqlmodel import select, Session
from database.models import User, Organizations, ProductCatalogue, Inventory
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

router = APIRouter()

#logger = logging.getLogger(__name__)

@router.post('/upload_product_catalogue')
async def upload_catalogue(
    file : UploadFile = File(...), 
    session : AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user)
):

    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, 
                                    detail="Only Excel files are supported.")

    try:
        content = await file.read()
        vfile_clone = io.BytesIO(content)
        df = pd.read_excel(vfile_clone)
        df = df.where(pd.notnull(df), None)
        catalogue_items_dict = df.to_dict(orient='records') # records is a list of dictionaries, where each dictionary represents a row in the DataFrame

        product_count = 0

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

    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"An error occurred while processing the file: {str(e)}")    

@router.put('/add_products')
async def add_products(
    is_manual : bool, 
    data : Optional[InventoryInput],
    file : Optional[UploadFile] = File(None), 
    session : AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user)
    ):

    get_user = await session.exec(select(User).where(User.email == current_user.sub))
    get_user = await get_user.first()

    try:
        if is_manual and not data:

         if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, 
                                        detail="Only Excel files are supported.")

            content = await file.read()
            vfile_name = io.BytesIO(content)
            df = pd.read_excel(vfile_name)
            df = df.where(pd.notnull(df), None)
            inventory_items = df.to_dict(orient='records') 

            items_barcode = [str(item["p_barcode"]) for item in inventory_items]
            catalogue_query = await session.exec(select(ProductCatalogue).where(ProductCatalogue.sku_or_barcode.in_(items_barcode)))
            catalogue_items = await catalogue_query.all()
            barcode_to_id_map = {item.sku_or_barcode: item.id for item in catalogue_items}

            items_location = [str(item["floor_no"]) for item in inventory_items]
            location_query = await session.exec(select(Inventory).where(Inventory.floor_no.in_(items_location)))
            location_items = await location_query.all()
            location_to_id_map = {item.floor_no: item.id for item in location_items}


            data = [Inventory(
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

            session.add_all(data)

        cat_id =await session.exec(select(ProductCatalogue).where(ProductCatalogue.sku_or_barcode == data.sku_or_barcode))
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

        return {"message": f"Successfully added {len(inventory_objects)} inventory items."}

    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"An error occurred while processing the file: {str(e)}")    

