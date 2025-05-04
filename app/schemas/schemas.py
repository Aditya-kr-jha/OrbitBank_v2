"""
Schema definitions for the banking application API.

This module contains Pydantic models that define the structure for:
- API request validation
- Response serialization
- Data transfer objects between API and service layer

The schemas are organized in three categories:
- Base: Common fields shared across create/update/read operations
- Create: Used for creating new resources (POST requests)
- Update: Used for partial updates (PATCH/PUT requests, with optional fields)
- Read: Used for responses returned to the client
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, EmailStr, Field, ConfigDict

from app.model_enums.model_enums import (
    UserStatus,
    AccountStatus,
    TransactionType,
    TransactionStatus,
    CurrencyCode
)


# --- Base Schemas ---

class UserBase(BaseModel):
    """Base fields for user data."""
    username: str = Field(..., min_length=3, max_length=50)
    full_name: str = Field(..., max_length=100)
    email: EmailStr
    phone_number: str = Field(..., max_length=20)
    address: Optional[str] = Field(None, max_length=255)
    pan_number: Optional[str] = Field(None, min_length=10, max_length=10)
    date_of_birth: Optional[date] = None


class BankBase(BaseModel):
    """Base fields for bank data."""
    name: str = Field(..., max_length=100)
    short_code: str = Field(..., min_length=2, max_length=10)


class BranchBase(BaseModel):
    """Base fields for branch data."""
    name: str = Field(..., max_length=100)
    address: str = Field(..., max_length=255)
    bank_id: int


class AccountTypeBase(BaseModel):
    """Base fields for account type data."""
    name: str = Field(..., max_length=50)
    minimum_balance: Decimal = Field(default=Decimal("0.0000"), ge=0, decimal_places=4)
    interest_rate: Decimal = Field(default=Decimal("0.00"), ge=0, decimal_places=2)


class AccountBase(BaseModel):
    """Base fields for account data."""
    owner_id: int
    branch_ifsc: str
    account_type_code: str
    currency_code: CurrencyCode


class TransactionBase(BaseModel):
    """Base fields for transaction data."""
    type: TransactionType
    status: TransactionStatus
    reference_number: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=255)


class EntryBase(BaseModel):
    """Base fields for accounting entry data."""
    account_id: int
    amount: Decimal = Field(..., decimal_places=4)
    currency_code: CurrencyCode
    transaction_id: Optional[int] = None


class TransferBase(BaseModel):
    """Base fields for fund transfer data."""
    transaction_id: int
    from_account_id: int
    to_account_id: int
    amount: Decimal = Field(..., gt=0, decimal_places=4)
    currency_code: CurrencyCode


# --- Create Schemas ---

class UserCreate(UserBase):
    """Schema for creating a new user."""
    password: str = Field(..., min_length=8)


class BankCreate(BankBase):
    """Schema for creating a new bank."""
    pass


class BranchCreate(BranchBase):
    """Schema for creating a new branch."""
    ifsc_code: str = Field(..., min_length=11, max_length=11)


class AccountTypeCreate(AccountTypeBase):
    """Schema for creating a new account type."""
    code: str = Field(..., min_length=3, max_length=10)


class AccountCreate(AccountBase):
    """Schema for creating a new account."""
    account_number: str = Field(..., min_length=5, max_length=20)
    balance: Decimal = Field(default=Decimal("0.0000"), ge=0, decimal_places=4)
    status: AccountStatus = Field(default=AccountStatus.ACTIVE)


class TransactionCreate(TransactionBase):
    """Schema for creating a new transaction."""
    pass


class EntryCreate(EntryBase):
    """Schema for creating a new accounting entry."""
    pass


class TransferCreate(TransferBase):
    """Schema for creating a new fund transfer."""
    pass


# --- Update Schemas ---

class UserUpdate(BaseModel):
    """Schema for updating user information."""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    full_name: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = Field(None, max_length=255)
    pan_number: Optional[str] = Field(None, min_length=10, max_length=10)
    date_of_birth: Optional[date] = None
    status: Optional[UserStatus] = None


class BankUpdate(BaseModel):
    """Schema for updating bank information."""
    name: Optional[str] = Field(None, max_length=100)
    short_code: Optional[str] = Field(None, min_length=2, max_length=10)


class BranchUpdate(BaseModel):
    """Schema for updating branch information."""
    name: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = Field(None, max_length=255)
    bank_id: Optional[int] = None


class AccountTypeUpdate(BaseModel):
    """Schema for updating account type information."""
    name: Optional[str] = Field(None, max_length=50)
    minimum_balance: Optional[Decimal] = Field(None, ge=0, decimal_places=4)
    interest_rate: Optional[Decimal] = Field(None, ge=0, decimal_places=2)


class AccountUpdate(BaseModel):
    """Schema for updating account information."""
    balance: Optional[Decimal] = Field(None, decimal_places=4)
    currency_code: Optional[CurrencyCode] = None
    status: Optional[AccountStatus] = None
    closed_at: Optional[datetime] = None


class TransactionUpdate(BaseModel):
    """Schema for updating transaction information."""
    status: Optional[TransactionStatus] = None
    reference_number: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    completed_at: Optional[datetime] = None


class EntryUpdate(BaseModel):
    """Schema for updating entry information. Entries are typically immutable."""
    pass


class TransferUpdate(BaseModel):
    """Schema for updating transfer information. Transfers are typically immutable."""
    pass


# --- Read Schemas ---

class UserRead(UserBase):
    """Schema for user data in responses."""
    id: int
    status: UserStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BankRead(BankBase):
    """Schema for bank data in responses."""
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BranchRead(BranchBase):
    """Schema for branch data in responses."""
    ifsc_code: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AccountTypeRead(AccountTypeBase):
    """Schema for account type data in responses."""
    code: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AccountRead(AccountBase):
    """Schema for account data in responses."""
    id: int
    account_number: str
    balance: Decimal
    status: AccountStatus
    opened_at: datetime
    closed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TransactionRead(TransactionBase):
    """Schema for transaction data in responses."""
    id: int
    initiated_at: datetime
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EntryRead(EntryBase):
    """Schema for accounting entry data in responses."""
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TransferRead(TransferBase):
    """Schema for transfer data in responses."""
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class UserPasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)

class DepositRequest(BaseModel):
    amount: Decimal
    description: str = None

class NewTransferRequest(BaseModel):
    from_account_id: int
    to_account_id: int
    amount: Decimal = Field(..., gt=0)
    description: str = None