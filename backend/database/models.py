from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
import uuid
from uuid import UUID
from datetime import date, datetime 
from enum import Enum
from pydantic import field_validator, model_validator

class OrderType(str, Enum):
    LOWSTOCK = "Low Stock"
    NEWORDER = "New Order"
    EMERGENCY = "Emergency"
    FAULTYPRODUCT = "Faulty Product"   

class ApprovalStatus(str, Enum):
    OUTFORDELIVERY = "out_for_delivery"
    PENDING = "pending"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"  

class PaymentStatus(str, Enum):
    ONDELIVERY = "on delivery"
    INADVANCE = "in advance"
    FAILED = "failed"


class User(SQLModel, table = True):
    id : UUID = Field(default_factory = uuid.uuid4, primary_key = True)
    org_id : UUID = Field(foreign_key = "organizations.id", default = None, nullable = True)
    name : str = Field(default = None, nullable = False)
    role : str = Field(default = None, nullable = False)
    email: str = Field(default = None, nullable = False)
    password : str = Field(default = None, nullable = False)

class SupplierOrganisationLink(SQLModel, table = True):
    id : UUID = Field(default_factory = uuid.uuid4, primary_key = True)
    supplier_id : UUID = Field(foreign_key = "suppliers.id", default = None, nullable = False)
    org_id : UUID = Field(foreign_key = "organizations.id", default = None, nullable = False)

class Organizations(SQLModel, table = True):
    id : UUID = Field(default_factory = uuid.uuid4, primary_key=True)
    name : str = Field(unique = True, default = None, nullable = False)
    email: str = Field(unique = True, default = None, nullable = False)
    suppliers : List["Suppliers"] = Relationship(back_populates = "organizations", link_model = SupplierOrganisationLink)

class Inventory(SQLModel, table = True):
    id : UUID = Field(default_factory = uuid.uuid4, primary_key = True)
    org_id : UUID = Field(foreign_key = "organizations.id", default = None, nullable = True)
    entry_date : datetime = Field(default_factory = datetime.now, nullable = True)
    entries_by : UUID = Field(foreign_key = "user.id", default = None, nullable = False)
    p_name : str = Field(default = None, nullable = False)
    p_mg : int = Field(default = 0, nullable = False)   
    p_quantity : int = Field(default = 0, nullable = False)
    mfct_date : date = Field(default = None, nullable = True)
    exp_date : date = Field(default = None, nullable = True)
    location_id : UUID = Field(foreign_key = "locations.id", default = None, nullable = False)
    batch_num : str = Field(default = None, nullable = True)
    min_stock_lvl : int = Field(default = 0, nullable = False)
    reorder_point : int = Field(default = 0, nullable = False)

    @field_validator('p_quantity', 'p_mg', 'min_stock_lvl', 'reorder_point')
    @classmethod
    def quantity_check(cls, v) -> int:
        if v < 0:
            raise ValueError("Value cannot be negative")
        return v

    @field_validator('mfct_date') 
    @classmethod
    def mfct_date_check(cls, v) -> date:
        if v and v > date.today():
            raise ValueError("Manufacturing date cannot be in the future")
        return v

    @model_validator(mode='after')
    def validation_business_rules(self) -> "Inventory":
            if self.mfct_date and self.exp_date:
                if self.exp_date < self.mfct_date:
                    raise ValueError("Expiry date cannot be before manufacturing date")
            return self


class Suppliers(SQLModel, table = True):
    id : UUID = Field(default_factory = uuid.uuid4, primary_key = True)
    name : str = Field(default = None, nullable = False)
    email : str = Field(unique = True, default = None, nullable = False)
    organizations : List["Organizations"] = Relationship(back_populates = "suppliers", link_model = SupplierOrganisationLink)

class Locations(SQLModel, table = True):
    id : UUID = Field(default_factory = uuid.uuid4, primary_key = True)
    org_id : UUID = Field(foreign_key = "organizations.id", default = None, nullable = False)
    floor_no : int = Field(default = 0, nullable = False)
    ward_no : str = Field(default = None, nullable = False)   
    shelf_no : str = Field(default = None, nullable = False)
    bin_id : str = Field(default = None, nullable = False)

class Orders(SQLModel, table = True):
    id : UUID = Field(default_factory = uuid.uuid4, primary_key = True)
    org_id : UUID = Field(foreign_key = "organizations.id", default = None, nullable = False)
    supplier_id : UUID = Field(foreign_key = "suppliers.id", default = None, nullable = False)
    approval_status : str = Field(default = ApprovalStatus.PENDING, nullable = False)
    order_type : str = Field(default = OrderType.LOWSTOCK, nullable = False)
    transfer_id : UUID = Field(foreign_key = "transactions.id", default = None, nullable = True)
    placed_on : datetime = Field(default_factory = datetime.now, nullable = True) 
    delivery_date : date = Field(default=None, nullable=True)
    excel_sheet_url : str = Field(default=None, nullable=True)

class Transactions(SQLModel, table = True):
    id : UUID = Field(default_factory = uuid.uuid4, primary_key = True)
    org_id : UUID = Field(foreign_key = "organizations.id", default = None, nullable = False)
    order_id : UUID = Field(foreign_key = "orders.id", default = None, nullable = False)
    total_product_cost : float = Field(default = 0.0, nullable = False)
    delivery_charges : float = Field(default = 0.0, nullable = False)
    tax_amount : float = Field(default = 0.0, nullable = False)
    total_cost : float = Field(default = 0.0, nullable = False)
    payment_status : str = Field(default = PaymentStatus.ONDELIVERY, nullable = False)
    transaction_date : datetime = Field(default_factory = datetime.now, nullable = True)

    @field_validator("payment_status")
    @classmethod
    def transaction_check(cls, v):

        if v.payment_status == PaymentStatus.FAILED:
                    v.transaction_date = None
                    
        expected_total = v.total_product_cost + v.delivery_charges + v.tax_amount
        if round(v.total_cost, 2) != round(expected_total, 2):
            raise ValueError(
                f"Financial Mismatch: Total cost ({v.total_cost}) "
                f"must equal sum of parts ({expected_total})"
            )
        return v

    @field_validator("total_product_cost", "delivery_charges", "tax_amount", "total_cost")
    @classmethod
    def product_cost_check(cls, v):
        if v < 0:
            raise ValueError(f"{v} cannot be negative")
        return v

    @model_validator(mode="after")
    def validate_totals(self) -> "Transactions":
        expected_total = self.total_product_cost + self.delivery_charges + self.tax_amount
        
        if round(self.total_cost, 2) != round(expected_total, 2):
            raise ValueError(
                f"Financial Mismatch: Total cost ({self.total_cost}) "
                f"must equal sum of parts ({expected_total})"
            )
        return self

class OrganisaionalSettings(SQLModel, table = True):
    id : UUID = Field(default_factory = uuid.uuid4, primary_key = True)
    org_id : UUID = Field(foreign_key = "organizations.id", default = None, nullable = False)
    low_stock_threshold : int = Field(default = 0, nullable = False)
    reorder_point : int = Field(default = 0, nullable = False)
    recieve_notifications : bool = Field(default = True, nullable = False)
    notification_email : str = Field(default = None, nullable = True)
    enable_auto_ordering : bool = Field(default = False, nullable = False)


