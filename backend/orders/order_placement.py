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
from feat.resource_checker import storage_finder

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
            order_type = "NEW ORDER",
            approval_status = "Approved",
            placed_on = datetime.now()
        )
        await session.add(save_orders)

    session.commit()
    return {"message": "Orders placed successfully."}

@router.get('/order_placement_details')
async def order_details(
    session : AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user)
):

    fetch_orders = await session.exec(select(Orders).where(Orders.org_id == current_user.org_id))
    fetch_orders = fetch_orders.all()

    if not fetch_orders:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                 detail=f"No order details found for the organization.")
    
    data = [item.model_dump() for item in fetch_orders]
    return file_generation(data, filename=f"order_detail", xl_name="Order Details")

@router.put('/order_approval')
async def order_approval(
    session : AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user),
):

    order_list = await session.exec(select(Orders).where(
                        Orders.org_id == current_user.org_id,
                        Orders.approval_status == "Pending",
                        Orders.order_status == "Pending").with_for_update())

    order_list = order_list.all()

    for order in order_list:
        order.approval_status = "Approved"
        await session.add(order)
    
    session.commit()
    return {"message": "All pending orders have been approved."}


@router.get('/view_order_history')
async def view_order_history(
    session : AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user)
):

    fetch_orders = await session.exec(select(Orders).where(
        Orders.org_id == current_user.org_id,
        Orders.order_status == "Delivered", 
        Orders.approval_status == "Approved"))

    fetch_orders = fetch_orders.all()

    if not fetch_orders:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                 detail=f"No order details found for the organization.")
    
    data = [item.model_dump() for item in fetch_orders]
    return file_generation(data, filename=f"order_history", xl_name="Order History")

@router.delete('/cancel_order_item')
async def cancel_order_item(
    name : str,
    session : AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user)
):

    order_item = await session.exec(select(Orders).where(
        Orders.org_id == current_user.org_id,
        Orders.name == name
    ).with_for_update())
    order_item = order_item.first()

    if not order_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                             detail="Order not found.")

    order_item.order_status = "CANCELLED"
    order_item.approval_status = "CANCELLED"
    session.add(order_item)
    await session.commit()
    return {"message": "Order cancelled successfully."}

@router.delete('/cancel_order')
async def cancel_order(
    session : AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user)
):

    order_list = await session.exec(select(Orders).where(
        Orders.org_id == current_user.org_id,
        Orders.order_status == "Pending"
        ).with_for_update())

    order_list = order_list.all()

    if not order_list:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                             detail="No recent orders found to cancel.")

    for order in order_list:
        order.order_status = "CANCELLED"
        order.approval_status = "CANCELLED"
        session.add(order)

    await session.commit()
    return {"message": "All pending orders have been cancelled successfully."}
