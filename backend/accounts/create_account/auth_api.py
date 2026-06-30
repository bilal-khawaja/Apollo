from fastapi import APIRouter, HTTPException, status, Depends, Body
from sqlmodel import select, Session
from database.models import User, Organizations
from database.setup import get_session
from database.schema import RegistrationInput, OrganisationDetails, UserCreationInput, ProductCatalogue
from ..auth.token import hash_password, check_hashed_password, get_current_user
from ..auth.token_handler import create_access_token
from sqlmodel.ext.asyncio.session import AsyncSession
from dotenv import load_dotenv
import os
load_dotenv()

router = APIRouter()

@router.post('/register_organisation')
async def signup(
    org : RegistrationInput, session : AsyncSession = Depends(get_session)):
    
    org.org_email = org.org_email.strip()
    org.password = org.password.strip()
    org.org_name = org.org_name.strip()
    org.admin_email = org.admin_email.strip()
    org.admin_name = org.admin_name.strip()
    
    query = await session.exec(select(Organizations).where(Organizations.email == org.org_email))
    query = query.first()
    if query:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail = "Email already registered")
      
    create = Organizations(
        name = org.org_name,
        email = org.org_email
    )    

    session.add(create)
    await session.flush()  # Ensure the organization is added and its ID is generated

    try:
        hashed_password = hash_password(org.password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=str(e))

    create_user = User(
        org_id = create.id,
        name = org.admin_name,
        role = "admin",
        email = org.admin_email,
        password = hashed_password
    )
    session.add(create_user)
    await session.commit()
    await session.refresh(create_user)

    access_token = create_access_token(
                            user_email=create_user.email, 
                            role=create_user.role, 
                            org_id=create.id, 
                            expiretime=int(os.getenv("EXPIRES_IN_MINUTES", 120))
    )
    return {
        "message" : "Organization created", 
        "access_token" : access_token,
        "token_type" : "bearer"
                        }

@router.post('/create_users')
async def create_users(
    user : UserCreationInput, session : AsyncSession = Depends(get_session)):
    
    user.email = user.email.strip()
    user.name = user.name.strip()
    user.role = user.role.strip()
    user.password = user.password.strip()
    
    query = await session.exec(select(User).where(User.email == user.email)).first()
    if query:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail = "Email already registered")
      
    try:
        hashed_password = hash_password(user.password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=str(e))

    create_user = User(
        name = user.name,
        role = user.role,
        email = user.email,
        password = hashed_password
    )
    session.add(create_user)
    await session.commit()
    await session.refresh(create_user)

    return {
        "message" : "User created"
        }

@router.post('/signin')
async def signin(
    email : str = Body(...), 
    password : str = Body(...), 
    session : AsyncSession = Depends(get_session)):
    
    query = await session.exec(select(User).where(User.email == email)).first()
    
    if not query:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail = f"Wrong email: {email}")

    if not check_hashed_password(password, query.password):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail = "Invalid password") 
  
    access_token = create_access_token(
                                        payload = {
                                            'sub' : query.email,
                                            'id' : query.id,
                                            'role' : query.role}
                                        )
    return {
            'message':'Login succesful',
            'access_token' : access_token,
            'token_type' : 'bearer'
            }   

@router.post('/create_catalogue')
async def create_catalogue(
    catalogue : ProductCatalogue,
    session : AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user)):

    check_catalogue = await session.exec(select(ProductCatalogue).where(ProductCatalogue.org_id == current_user.org_id)).first()
    
    if check_catalogue:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail = "Catalogue already exists for this organization")

    create_catalogue = ProductCatalogue(
        org_id = current_user.org_id,
        p_name = catalogue.p_name,
        p_mg = catalogue.p_mg,
        sku_or_barcode = catalogue.sku_or_barcode,
        strength = catalogue.strength,
        unit_type = catalogue.unit_type,
        manufacturer = catalogue.manufacturer
    )
    session.add(create_catalogue)
    await session.commit()
    await session.refresh(create_catalogue)
    return {
        "message" : "Product catalogue created"
    }

    





