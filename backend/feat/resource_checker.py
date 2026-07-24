import uuid
from database.models import Inventory, Locations, LowStock, InventoryStorageLink, Organizations, User
from typing import Optional
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from fastapi import HTTPException, status, Depends
from database.schema import UpdateInventory
from datetime import datetime
from uuid import UUID
from .worker_setup import celery_app
from database.setup import get_session
from sqlmodel.ext.asyncio.session import AsyncSession
from .webhooks_service import get_n8n_url, N8nEndpoints
import asyncio
from database.setup import engine
from sqlalchemy.orm import defer
import httpx
from collections import defaultdict

async def check_stock_levels(session : AsyncSession, data : UpdateInventory):
    """ 
    Function to check stock levels if the levels are low it stores the items in a seperate table for tracking and to later send email for the re-ordering.
    """

    fetch_product = await session.exec(select(Inventory).where(Inventory.p_name == data.p_name))
    fetch_product = fetch_product.first()

    if fetch_product.p_quantity < fetch_product.min_stock_lvl:

        low_stock_record = LowStock(
            org_id = fetch_product.org_id,
            inventory_id = fetch_product.id,
            name = fetch_product.p_name,
            strength = str(fetch_product.p_mg),
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

async def storage_finder(session: AsyncSession, category: str, quantity : int, inventory_id : uuid.UUID, org_id : uuid.UUID):
    """
    Function to find a suitable storage location based on category and available space.
    If the current location is full, it will look for another location with available space.
    """
    storage = await session.exec(select(Locations)
                .where(Locations.category == category)
                .order_by(Locations.priority_score.asc(),
                Locations.id.asc()
                )
            )

    storage = storage.all()

    for s in storage:
            available_space = s.max_capacity - s.current_occupancy
            
            # Only proceed if this location has actual room
            if available_space > 0:
                quantity_to_store = min(quantity, available_space)
                
                # Update the occupancy and decrement remaining quantity
                s.current_occupancy += quantity_to_store
                quantity -= quantity_to_store

                # Create the link record
                link_table = InventoryStorageLink(
                    org_id=s.org_id,
                    inventory_id=inventory_id,
                    location_id=s.id
                )
                session.add(link_table)

            # Stop looking for locations once we've fully allocated the inventory
            if quantity <= 0:
                break

    return None

    
@celery_app.task(bind=True, max_retries=3)
def process_low_stock_items(self):
    try:
        return asyncio.run(run_process_low_stock_items(self))
    finally:
        asyncio.run(engine.dispose())


async def run_process_low_stock_items(task_self):
    async with AsyncSession(engine) as session:
        fetch_low_stock_items = await session.exec(
            select(LowStock).where(LowStock.order_placed == False)
        )

        all_items = fetch_low_stock_items.all()
        if not all_items:
            return "No low stock items found to process."

        url = get_n8n_url(N8nEndpoints.LOW_STOCK)

        # Organising items by organization id for batch processing
        items_by_org = defaultdict(list)
        for item in all_items:
            items_by_org[item.org_id].append(item)

        total_notified = 0

        for org_id, items in items_by_org.items():

            # Fetch organization and admin details
            org = await session.exec(select(Organizations).where(Organizations.id == org_id))
            org = org.first()

            admin = await session.exec(select(User).where(User.org_id == org_id, User.role == "admin"))
            admin = admin.first()

            org_name = org.name if org else "Unknown Organization"
            admin_name = admin.name if admin else "Admin"

            # Prepare the data to send to n8n's file generation endpoint
            org_data = [
                {
                    "product_name": item.name,
                    "strength": item.strength,
                }
                for item in items
            ]

            # Prepare custom headers and file payload for the request to n8n's email service endpoint
            # Using custom header isntead of sending b=data in body because it will be dropped by n8n if the file is sent in the body of the request
            custom_headers = {
                "x-admin-name": str(admin_name),
                "x-organization-name": str(org_name),
            }

            # Helper function to generate the file for workflow B
            file_generation_content = await generate_file_for_workflowb(org_data)
            files_payload = {
                            "file": ("low_stock_report.xlsx", file_generation_content, 
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                        }
                        
            # Calling the n8n webhook for low stock email
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(url, headers=custom_headers, files = files_payload, timeout=30.0)

                    if response.status_code != 200:
                        print(f"n8n Error Body for Org {org_id}: {response.text}")
                        raise RuntimeError(f"n8n webhook failed with status code {response.status_code}")

                except httpx.RequestError as e:
                    await session.rollback()
                    raise task_self.retry(exc=e, countdown=60)

                except Exception as exc:
                    await session.rollback()
                    raise task_self.retry(exc=exc, countdown=60)

        return f"Successfully notified n8n for {total_notified} items across {len(items_by_org)} org(s)."

async def generate_file_for_workflowb(data : list[dict], timeout : float = 30.0):

    url = get_n8n_url(N8nEndpoints.FILE_GENERATION)
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=data, timeout=timeout)
        
        if response.status_code != 200:
            raise RuntimeError(f"Workflow A failed to generate Excel file: {response.text}")

        # Return the raw binary content
        return response.content

