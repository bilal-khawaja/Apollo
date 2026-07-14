from fastapi import APIRouter, HTTPException, status, Depends, Body, UploadFile, File
from sqlmodel import select
from database.models import User, Organizations, Orders, Suppliers
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
from feat.resource_checkup import storage_finder

router = APIRouter()

# For custom order placement, we will create a new endpoint that accepts an Excel file containing order details.
#  The endpoint will read the file, validate the data, and then place the orders in the database. 
# (Order type = NEW ORDER)

@router.post('/place_order')
async def place_order(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user)
):

    order_list = await file_explorer(file, clean_headers=True)

    for order in order_list:
        sup = await session.exec(select(Suppliers).where(Suppliers.email == order["supplier_email"]))
        sup = sup.first()

        if not sup:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                 detail=f"Supplier with email {order['supplier_email']} not found.")
        
        save_orders = Orders(
            org_id = current_user.org_id,
            supplier_id = sup.id,
            order_type = order["order_type"],
            approval_status = "Approved",
            placed_on = datetime.now()
        )
        await session.add(save_orders)

    session.commit()
    return {"message": "Orders placed successfully."}

@router.get('/order_details')
async def order_details(
    session : AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user)
):

    fetch_orders = await session.exec(select(Orders).where(Orders.org_id == current_user.org_id))
    fetch_orders = fetch_orders.all()

    if not fetch_orders:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                 detail=f"No orders found for the organization.")
    
    data = [item.model_dump() for item in fetch_orders]
    return file_generation(data, filename=f"order_detail", xl_name="Order Details")