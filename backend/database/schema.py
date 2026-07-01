from sqlmodel import SQLModel, Field
from typing import Optional, List
from pydantic import field_validator 
import re
from datetime import date, datetime

class UserPayload(SQLModel):
    sub: str
    role: str
    org_id: str
    exp: int




class RegistrationInput(SQLModel):
    org_name : str
    org_email : str
    admin_name : str
    admin_email : str
    password : str

    @field_validator('org_email', 'admin_email')
    @classmethod
    def email_must_be_valid(cls, v):    
        if not re.search(r"\w+@(\w+\.)?\w+\.(com)$",v, re.IGNORECASE):
            raise ValueError("Email must be in valid format and end with .com (e.g., user@example.com)")
        else:
            return v

                        
    @field_validator('password')    
    @classmethod
    def password_must_be_strong(cls, p):
             if not re.search(r"^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[!@#$%&*^_-])[A-Za-z\d!@#$%^&_*-]{5,}$",p):
                 raise ValueError("Password must be at least 5 characters long and contain: 1 uppercase letter, 1 lowercase letter, 1 digit, and 1 special character (!@#$%&*^_-)")
             else:
                    return p  

class UserCreationInput(SQLModel):
    name : str
    email : str
    role : str
    password : str

    @field_validator('email')
    @classmethod
    def email_must_be_valid(cls, v):    
        if not re.search(r"\w+@(\w+\.)?\w+\.(com)$",v, re.IGNORECASE):
            raise ValueError("Email must be in valid format and end with .com (e.g., user@example.com)")
        else:
            return v

    @field_validator('password')
    @classmethod
    def password_must_be_strong(cls, p):
                if not re.search(r"^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[!@#$%&*^_-])[A-Za-z\d!@#$%^&_*-]{5,}$",p):
                    raise ValueError("Password must be at least 5 characters long and contain: 1 uppercase letter, 1 lowercase letter, 1 digit, and 1 special character (!@#$%&*^_-)")
                else:
                        return p    

# For organization creation and update, which will happen after account creation, we will use this model to validate the input data.
class OrganisationDetails(SQLModel):
    name : str
    admin_email : str
    suppliers : List[str] = None
    supplier_emails : List[str] = None
    @field_validator('admin_email')
    @classmethod
    def email_must_be_valid(cls, v):    
        if not re.search(r"\w+@(\w+\.)?\w+\.(com)$",v, re.IGNORECASE):
            raise ValueError("Email must be in valid format and end with .com (e.g., user@example.com)")
        else:
            return v

# For staff members responsible for inventory management, we will use this model to create their data in db and further send them invitation to have their accounts
# created.

class InvitationDetails(SQLModel):
    name : str
    email : str
    role : str
    @field_validator('email')
    @classmethod
    def email_must_be_valid(cls, v):    
        if not re.search(r"\w+@(\w+\.)?\w+\.(com)$",v, re.IGNORECASE):
            raise ValueError("Email must be in valid format and end with .com (e.g., user@example.com)")
        else:
            return v

# For data entry in inventory, we will use this model to validate the input data.
class InventoryInput(SQLModel):
    p_name : str
    p_mg : int
    p_quantity : int
    mfct_date : date
    exp_date : date
#    location_id : str
    batch_num : str


# Storage rooms info for Locations table
