from contextlib import asynccontextmanager
from typing import List
from fastapi import FastAPI, Depends, HTTPException, status
from sqlmodel import select
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlmodel.ext.asyncio.session import AsyncSession
from database.setup import get_session, init_db
from dotenv import load_dotenv
from accounts.create_account.auth_api import router as auth_api
from inventory.inventory_setup import router as inventory
from accounts.create_account.acc_setup import router as acc_setup
load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Initialising PostgreSQL Database...")
    await init_db()
    yield
    print("Cleaning up resources...")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_api, prefix="/auth", tags=["Authentication"])
app.include_router(inventory, prefix="/inventory", tags=["Inventory Management"])
app.include_router(acc_setup, prefix="/account", tags=["Account Setup"])
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    errors = [err['msg'] for err in exc.errors()] 
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"message": ", ".join(errors)},
    )