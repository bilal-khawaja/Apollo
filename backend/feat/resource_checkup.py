from database.models import Inventory, Locations, LowStock
from typing import Optional
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from fastapi import HTTPException, status, Depends
from databse.schema import UpdateInventory
from datetime import datetime

async def check_stock_levels(session : AsyncSession, data : UpdateInventory):
    """ 
    Function to check stock levels if the levels are low an email is sent to Admin
    and generates a record in databse model for the items that need to be ordered.
    """

    fetch_product = await session.exec(select(Inventory).where(Inventory.p_name == data.p_name))
    fetch_product = fetch_product.first()

    if fetch_product.p_quantity < fetch_product.min_stock_lvl:
        # Logic to send email to Admin

        low_stock_record = LowStock(
            org_id = fetch_product.org_id,
            inventory_id = fetch_product.id,
            name = fetch_product.p_name,
            strength = fetch_product.strength,
            created_on = datetime.now()
        )
        session.add(low_stock_record)
        await session.commit()

        return {
            "status": "low_stock", 
            "message": f"Stock is low ({fetch_product.p_quantity}). Admin notified and low stock record created."
        }

    else:
        return {
            "status": "sufficient_stock", 
            "message": f"Stock is sufficient ({fetch_product.p_quantity}). No action needed."
        }



async def storage_finder(session: AsyncSession, category: str):
    """
    Function to find a suitable storage location based on category and available space.
    If the current location is full, it will look for another location with available space.
    """

    storage = await session.exec(select(Locations)
                .where(Locations.category == category)
                .order_by(Locations.priority_score.asc()))
                
    storage = storage.all()

    for s in storage:
        if s.current_occupancy < s.max_capacity:
            return s  

    return None  


# for checking storage unit space and if the space is low inventory items are stored in another unit and an email is
#  sent to Admin to notify about the low space in the storage unit.