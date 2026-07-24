from fastapi import APIRouter, HTTPException, status, Depends, Body, UploadFile, File
from sqlmodel import select
from database.models import User, Organizations, Inventory, Locations, ProductCatalogue, InventoryStorageLink
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
from feat.xlx_processing_generation import file_processor, file_generation
from feat.resource_checker import storage_finder, check_stock_levels
from feat.caching import validate_idempotency
from feat.webhooks_service import get_n8n_url, N8nEndpoints

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

    for item in inventory_items:

        fetch_item = id_map.get(item["p_name"])

        if not fetch_item:
            continue  # Skip if the product is not found in the catalogue

        incoming_quantity = int(item["quantity"])
        new_inventory = Inventory(
                    **{
                        **item,
                        "org_id": current_user.org_id,
                        "catalogue_id": fetch_item.id,
                        "entry_date": datetime.now(),
                        "p_name": item["p_name"],
                        "p_mg": int(item["p_mg"]),
                        "p_quantity": incoming_quantity,

                        "mfct_date": datetime.strptime(item["mfct_date"], "%Y-%m-%d")
                        if isinstance(item["mfct_date"], str) else item["mfct_date"],

                        "exp_date": datetime.strptime(item["exp_date"], "%Y-%m-%d")
                        if isinstance(item["exp_date"], str) else item["exp_date"],

                        "batch_num": str(item["batch_num"]),
                        "entries_by": get_user.id,
                        "min_stock_lvl": int(item["min_stock_lvl"]),
                        "reorder_point": int(item["reorder_point"])
                    }
                )
        session.add(new_inventory)
        await session.flush()  # Flush to get the inventory_id for linking

        store_in_locations = await storage_finder(session, fetch_item.category, incoming_quantity, new_inventory.id, current_user.org_id)

    await session.commit()
    return {"message": f"Successfully added products inventory items."}

@router.post('/scan_products_input')
async def scan_products(
    data : InventoryInput,
    session : AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user)
    ):

    get_user = await session.exec(select(User).where(User.email == current_user.sub))
    get_user =  get_user.first()


    cat = await session.exec(select(ProductCatalogue).where(ProductCatalogue.sku_or_barcode == data.sku_or_barcode))
    cat =  cat.first()

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


@router.put('/edit_inventory')
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

            update_info = await session.exec(select(Inventory).where(Inventory.id == id).with_for_update())
            update_info =  update_info.first()

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


# For updating the inventory quantity based on barcode and action type (consume or add), with the help
# of pessimistic locking to avoid race conditions.
@router.put('/update_inventory_quantity')
async def update_inventory_quantity( 
    barcode : str,
    action_type : str,
    location_id : uuid.UUID,
    quantity : int,
    session : AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user),
    scan_id = Depends(validate_idempotency)
):

    try:
        check_barcode = await session.exec(select(ProductCatalogue).where(ProductCatalogue.sku_or_barcode == barcode).with_for_update())
        product = check_barcode.first()

        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        
        inventory_lookup = await session.exec(select(Inventory).where(
            Inventory.catalogue_id == product.id).with_for_update())
        inventory_item = inventory_lookup.first()

        location_lookup = await session.exec(select(Locations).where(Locations.id == location_id).with_for_update())
        location = location_lookup.first()

        if not inventory_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                             detail="Inventory item not found")
        if action_type == "consume":
            inventory_item.p_quantity -= quantity
            location.current_occupancy -= quantity
        
        else:
            inventory_item.p_quantity += quantity
            location.current_occupancy += quantity

        quantity_check = await check_stock_levels(session, inventory_item)

        await session.commit()
        return {"message": f"Successfully updated inventory quantity for product '{product.name}'."}

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get('/view_inventory')
async def view_inventory(
    session : AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user)
):

    fetch_inventory = await session.exec(select(Inventory).where(Inventory.org_id == current_user.org_id))
    fetch_inventory = fetch_inventory.all()

    if not fetch_inventory:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                             detail="No inventory items found for your organization.")

    data = [item.model_dump(mode='json') for item in fetch_inventory]
    return  await file_generation(data, filename="inventory_data.xlsx")


@router.delete('/delete_all_inventory')
async def delete_all_inventory(
    session : AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user)
):
    try:
        delete_query = await session.exec(select(Inventory).where(Inventory.org_id == current_user.org_id))
        delete_items = delete_query.all()

        if not delete_items:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                             detail="No inventory items found for your organization.")

        for item in delete_items:
            await session.delete(item)

        await session.commit()
        return {"message": "All inventory items deleted successfully."}

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

