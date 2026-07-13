from fastapi import APIRouter, HTTPException, status, Depends, Body, UploadFile, File
from sqlmodel import select, Session
from database.models import User, Organizations, Inventory, Locations, ProductCatalogue
from database.setup import get_session
from accounts.auth.token import  get_current_user
from sqlmodel.ext.asyncio.session import AsyncSession
import pandas as pd
import io
from database.schema import InventoryInput, UpdateInventory
import uuid
from uuid import UUID
from datetime import datetime
from sqlmodel import insert
import logging
from typing import Optional
from feat.xlx_processing_generation import file_processor
router = APIRouter()

#logger = logging.getLogger(__name__)


@router.post('/bulk_save_products')
async def add_products(
    file : UploadFile = File(...), 
    session : AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user)
    ):

    get_user = await session.exec(select(User).where(User.email == current_user.sub))
    get_user = get_user.first()

    inventory_items = await file_processor(file, clean_headers=True)

    # For fetching catalogue ID
    items_name = [str(item["p_name"]) for item in inventory_items]
    catalogue_query = await session.exec(select(ProductCatalogue).where(ProductCatalogue.name.in_(items_name)))
    catalogue_items =  catalogue_query.all()
    id_map = {item.name: item for item in catalogue_items}

    # For setting location ID
    category_list = list({item.category for item in catalogue_items})
    catalogue_location_relation = await session.exec(select(Locations).where(Locations.category.in_(category_list)))
    catalogue_location_relation = catalogue_location_relation.all()

    # Composite key mapping for location based on category, ward_no, shelf_no, bin_id, and floor_no
    catalogue_to_id_map = {f"{loc.category}|{loc.ward_no}|{loc.shelf_no}|{loc.bin_id}|{loc.floor_no}": loc.id
                                                             for loc in catalogue_location_relation}
    bulk_entry = []
    for item in inventory_items:
        fetch_item = id_map.get(item["p_name"])
        if not fetch_item:
            continue  # Skip if the product is not found in the catalogue

        location_lookup_key = next(
            (loc for loc in catalogue_location_relation if loc.category == fetch_item.category),
            None
        )

        if location_lookup_key:
            composite_key = f"{location_lookup_key.category}|{location_lookup_key.ward_no}|{location_lookup_key.shelf_no}|{location_lookup_key.bin_id}|{location_lookup_key.floor_no}"
            target_location_id = catalogue_to_id_map.get(composite_key)
            if target_location_id:
                bulk_entry.append(
                    Inventory(
                        **{
                            **item,
                            "org_id": current_user.org_id,
                            "catalogue_id": fetch_item.id,
                            "entry_date": datetime.now(),
                            "p_name": item["p_name"],
                            "p_mg": int(item["p_mg"]),
                            "p_quantity": int(item["quantity"]),

                            "mfct_date": datetime.strptime(item["mfct_date"], "%Y-%m-%d")
                            if isinstance(item["mfct_date"], str) else item["mfct_date"],

                            "exp_date": datetime.strptime(item["exp_date"], "%Y-%m-%d")
                            if isinstance(item["exp_date"], str) else item["exp_date"],

                            "location_id": target_location_id, 
                            "batch_num": str(item["batch_num"]),
                            "entries_by": get_user.id,
                            "min_stock_lvl": int(item["min_stock_lvl"]),
                            "reorder_point": int(item["reorder_point"])
                        }
                    )
                )
    if bulk_entry:
        session.add_all(bulk_entry)

    else:
        
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                 detail=f"Location not found for product {item['p_name']} with category {location_lookup_key.category} in ProductCatalogue.")

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


    cat = await session.exec(select(ProductCatalogue).where(ProductCatalogue.sku_or_barcode == data.sku_or_barcode))
    cat = await cat.first()

    fetch_location = await session.exec(select(Locations).where(Locations.category == cat.category))
    fetch_location =  fetch_location.first()

    inventory_objects =  Inventory(
        org_id = current_user.org_id,
        catalogue_id = cat.id,
        entry_date = datetime.now(),
        entries_by = get_user.id,
        p_name = data.p_name,
        p_mg = data.p_mg,
        p_quantity = data.p_quantity,
        mfct_date = data.mfct_date,
        exp_date = data.exp_date,
        location_id = fetch_location.id,
        batch_num = data.batch_num,
        min_stock_lvl = data.min_stock_lvl,
        reorder_point = data.reorder_point
    )
    session.add(inventory_objects)
    await session.commit()

    return {"message": f"Successfully added products inventory items."}


@router.put('/update_inventory')
async def update_inventory(
    data : UpdateInventory,
    id : Optional[UUID] = None,
    session : AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user)
):
    try:
        if not id:
            update_info = Inventory(
                org_id = current_user.org_id,
                p_name = data.p_name,
                p_mg = data.p_mg,
                p_quantity = data.p_quantity,
                mfct_date = data.mfct_date,
                exp_date = data.exp_date,
                batch_num = data.batch_num,
                min_stock_lvl = data.min_stock_lvl,
                reorder_point = data.reorder_point
            )
            session.add(update_info)

        else:

            update_info = await session.exec(select(Inventory).where(Inventory.id == id))
            update_info = await update_info.first()

            if not update_info:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                             detail="Inventory item not found")
            
            fields_to_update = data.dict(exclude_unset=True)
            for field, value in fields_to_update.items():
                setattr(update_info, field, value)

        await session.commit()
        return {"message": f"Successfully updated inventory item."} 
    
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))