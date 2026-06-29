from fastapi import APIRouter, HTTPException, status, Depends, Body
from sqlmodel import select, Session
from database.models import User
from database.setup import get_session
from database.schema import UserInput, OrganisationDetails, InvitationDetails
from .auth.token import hash_password, check_hashed_password
from .auth.token_handler import create_access_token

router = APIRouter()

@router.post('/signup')
def signup(
    user : UserInput, session : Session = Depends(get_session)):
    user.email = user.email.strip()
    user.password = user.password.strip()
    query = session.exec(select(User).where(User.email == user.email)).first()
    if query:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail = "Email already registered")
    
    try:
        hashed_password = hash_password(user.password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=str(e))
    
    create = User(
        email = user.email,
        password = hashed_password
    )    
    
    session.add(create)
    session.commit()
    session.refresh(create)
    return {"message" : "User created"}

@router.post('/signin')
def signin(
    email : str = Body(...), 
    password : str = Body(...), 
    session : Session = Depends(get_session)):
    
    query = session.exec(select(User).where(User.email == email)).first()
    
    if not query:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail = f"Wrong email: {email}")

    if not check_hashed_password(password, query.password):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail = "Invalid password") 
  
    access_token = create_access_token(
                                        data = {
                                            'sub' : query.email,
                                            'id' : query.id,
                                            'role' : query.role}
                                        )
    return {
            'message':'Login succesful',
            'access_token' : access_token,
            'token_type' : 'bearer'
            }   

