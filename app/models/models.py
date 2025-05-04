from datetime import date, datetime, timezone
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship, select
from decimal import Decimal


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True)
    hashed_password: str
    full_name: str
    email: str = Field(unique=True)
    phone_number: str = Field(unique=True)
    address: Optional[str] = None
    pan_number: Optional[str] = Field(default=None, unique=True)
    date_of_birth: Optional[date] = None
    status: str = Field(default="ACTIVE")
    password_changed_at: datetime = Field(default_factory=lambda: datetime(1, 1, 1, tzinfo=timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    accounts: List["Account"] = Relationship(back_populates="owner")


class Bank(SQLModel, table=True):
    __tablename__ = "banks"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    short_code: str = Field(unique=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    branches: List["Branch"] = Relationship(back_populates="bank")


class Branch(SQLModel, table=True):
    __tablename__ = "branches"

    ifsc_code: str = Field(primary_key=True)
    bank_id: int = Field(foreign_key="banks.id")
    name: str
    address: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    bank: Bank = Relationship(back_populates="branches")
    accounts: List["Account"] = Relationship(back_populates="branch")


class AccountType(SQLModel, table=True):
    __tablename__ = "account_types"

    code: str = Field(primary_key=True)
    name: str = Field(unique=True)
    minimum_balance: Decimal = Field(default=0.0000)
    interest_rate: Decimal = Field(default=0.00)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    accounts: List["Account"] = Relationship(back_populates="account_type")


class Account(SQLModel, table=True):
    __tablename__ = "accounts"

    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="users.id")
    account_number: str = Field(unique=True)
    branch_ifsc: str = Field(foreign_key="branches.ifsc_code")
    account_type_code: str = Field(foreign_key="account_types.code")
    balance: Decimal = Field(default=0.0000)
    currency_code: str
    status: str = Field(default="ACTIVE")
    opened_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    closed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    owner: User = Relationship(back_populates="accounts")
    branch: Branch = Relationship(back_populates="accounts")
    account_type: AccountType = Relationship(back_populates="accounts")
    entries: List["Entry"] = Relationship(back_populates="account")
    from_transfers: List["Transfer"] = Relationship(back_populates="from_account", sa_relationship_kwargs={
        "foreign_keys": "[Transfer.from_account_id]"})
    to_transfers: List["Transfer"] = Relationship(back_populates="to_account",
                                                  sa_relationship_kwargs={"foreign_keys": "[Transfer.to_account_id]"})


class Transaction(SQLModel, table=True):
    __tablename__ = "transactions"

    id: Optional[int] = Field(default=None, primary_key=True)
    type: str
    status: str
    reference_number: Optional[str] = Field(default=None, unique=True)
    description: Optional[str] = None
    initiated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    entries: List["Entry"] = Relationship(back_populates="transaction")
    transfer: Optional["Transfer"] = Relationship(back_populates="transaction")


class Entry(SQLModel, table=True):
    __tablename__ = "entries"

    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="accounts.id")
    amount: Decimal
    currency_code: str
    transaction_id: Optional[int] = Field(default=None, foreign_key="transactions.id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    account: Account = Relationship(back_populates="entries")
    transaction: Optional[Transaction] = Relationship(back_populates="entries")


class Transfer(SQLModel, table=True):
    __tablename__ = "transfers"

    id: Optional[int] = Field(default=None, primary_key=True)
    transaction_id: int = Field(foreign_key="transactions.id", unique=True)
    from_account_id: int = Field(foreign_key="accounts.id")
    to_account_id: int = Field(foreign_key="accounts.id")
    amount: Decimal
    currency_code: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    transaction: Transaction = Relationship(back_populates="transfer")
    from_account: Account = Relationship(back_populates="from_transfers",
                                         sa_relationship_kwargs={"foreign_keys": "[Transfer.from_account_id]"})
    to_account: Account = Relationship(back_populates="to_transfers",
                                       sa_relationship_kwargs={"foreign_keys": "[Transfer.to_account_id]"})

def get_user(username: str, session) -> Optional[User]:
    statement = select(User).where(User.username == username)
    user = session.exec(statement).first()
    return user