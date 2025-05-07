from datetime import date, datetime, timezone
from typing import Optional, List

import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel, Field, Relationship, select
from decimal import Decimal

from app.model_enums.model_enums import (
    UserStatus,
    CurrencyCode,
    AccountStatus,
    TransactionType,
    TransactionStatus,
)


class UserBeneficiaryLink(SQLModel, table=True):
    """Association table for the many-to-many relationship between users and their beneficiaries."""

    __tablename__ = "user_beneficiary_link"

    user_id: int = Field(foreign_key="users.id", primary_key=True)
    beneficiary_user_id: int = Field(foreign_key="users.id", primary_key=True)
    # Optional: Add a timestamp for when the beneficiary was added
    added_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class User(SQLModel, table=True):
    """User model representing bank customers."""

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
    status: UserStatus = Field(default=UserStatus.ACTIVE)
    password_changed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=sqlalchemy.TIMESTAMP(timezone=True),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=sqlalchemy.TIMESTAMP(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=sqlalchemy.TIMESTAMP(timezone=True),
    )

    # Existing relationship
    accounts: List["Account"] = Relationship(back_populates="owner")

    # --- New Beneficiary Relationships ---

    # Represents the list of users this user has added as beneficiaries
    beneficiaries: List["User"] = Relationship(
        back_populates="benefactors",  # Link to the relationship on the other side
        link_model=UserBeneficiaryLink,
        sa_relationship_kwargs=dict(
            primaryjoin="User.id==UserBeneficiaryLink.user_id",  # Join User.id with the 'owner' side of the link
            secondaryjoin="User.id==UserBeneficiaryLink.beneficiary_user_id",  # Join the 'beneficiary' side of the link back to User.id
            lazy="selectin",
        ),
    )

    # Represents the list of users who have added this user as their beneficiary
    benefactors: List["User"] = Relationship(
        back_populates="beneficiaries",  # Link to the relationship on the other side
        link_model=UserBeneficiaryLink,
        sa_relationship_kwargs=dict(
            primaryjoin="User.id==UserBeneficiaryLink.beneficiary_user_id",  # Join User.id with the 'beneficiary' side of the link
            secondaryjoin="User.id==UserBeneficiaryLink.user_id",  # Join the 'owner' side of the link back to User.id
            lazy="selectin",
        ),
    )


class Bank(SQLModel, table=True):
    """Bank institution model."""

    __tablename__ = "banks"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    short_code: str = Field(unique=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=sqlalchemy.TIMESTAMP(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=sqlalchemy.TIMESTAMP(timezone=True),
    )

    branches: List["Branch"] = Relationship(back_populates="bank")


class Branch(SQLModel, table=True):
    """Bank branch model with IFSC code as identifier."""

    __tablename__ = "branches"

    ifsc_code: str = Field(primary_key=True)
    bank_id: int = Field(foreign_key="banks.id")
    name: str
    address: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=sqlalchemy.TIMESTAMP(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=sqlalchemy.TIMESTAMP(timezone=True),
    )

    bank: Bank = Relationship(back_populates="branches")
    accounts: List["Account"] = Relationship(back_populates="branch")


class AccountType(SQLModel, table=True):
    """Types of bank accounts with associated rules."""

    __tablename__ = "account_types"

    code: str = Field(primary_key=True)
    name: str = Field(unique=True)
    minimum_balance: Decimal = Field(default=Decimal("0.0000"))
    interest_rate: Decimal = Field(default=Decimal("0.00"))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=sqlalchemy.TIMESTAMP(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=sqlalchemy.TIMESTAMP(timezone=True),
    )

    accounts: List["Account"] = Relationship(back_populates="account_type")


class Account(SQLModel, table=True):
    """Bank account model."""

    __tablename__ = "accounts"

    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="users.id")
    account_number: str = Field(unique=True)
    branch_ifsc: str = Field(foreign_key="branches.ifsc_code")
    account_type_code: str = Field(foreign_key="account_types.code")
    balance: Decimal = Field(default=Decimal("0.0000"))
    currency_code: CurrencyCode
    status: AccountStatus = Field(default=AccountStatus.ACTIVE)
    opened_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=sqlalchemy.TIMESTAMP(timezone=True),
    )
    closed_at: Optional[datetime] = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=sqlalchemy.TIMESTAMP(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=sqlalchemy.TIMESTAMP(timezone=True),
    )

    owner: User = Relationship(back_populates="accounts")
    branch: Branch = Relationship(back_populates="accounts")
    account_type: AccountType = Relationship(back_populates="accounts")
    entries: List["Entry"] = Relationship(back_populates="account")
    from_transfers: List["Transfer"] = Relationship(
        back_populates="from_account",
        sa_relationship_kwargs={"foreign_keys": "[Transfer.from_account_id]"},
    )
    to_transfers: List["Transfer"] = Relationship(
        back_populates="to_account",
        sa_relationship_kwargs={"foreign_keys": "[Transfer.to_account_id]"},
    )


class Transaction(SQLModel, table=True):
    """Financial transaction record."""

    __tablename__ = "transactions"

    id: Optional[int] = Field(default=None, primary_key=True)
    type: TransactionType
    status: TransactionStatus
    reference_number: Optional[str] = Field(default=None, unique=True)
    description: Optional[str] = None
    initiated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=sqlalchemy.TIMESTAMP(timezone=True),
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        sa_type=sqlalchemy.TIMESTAMP(timezone=True),  # Add this line
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=sqlalchemy.TIMESTAMP(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=sqlalchemy.TIMESTAMP(timezone=True),
    )

    entries: List["Entry"] = Relationship(back_populates="transaction")
    transfer: Optional["Transfer"] = Relationship(back_populates="transaction")


class Entry(SQLModel, table=True):
    """Accounting entry for tracking money movements."""

    __tablename__ = "entries"

    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="accounts.id")
    amount: Decimal
    currency_code: CurrencyCode
    transaction_id: Optional[int] = Field(default=None, foreign_key="transactions.id")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=sqlalchemy.TIMESTAMP(timezone=True),
    )

    account: Account = Relationship(back_populates="entries")
    transaction: Optional[Transaction] = Relationship(back_populates="entries")


class Transfer(SQLModel, table=True):
    """Fund transfer between accounts."""

    __tablename__ = "transfers"

    id: Optional[int] = Field(default=None, primary_key=True)
    transaction_id: int = Field(foreign_key="transactions.id", unique=True)
    from_account_id: int = Field(foreign_key="accounts.id")
    to_account_id: int = Field(foreign_key="accounts.id")
    amount: Decimal
    currency_code: CurrencyCode
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=sqlalchemy.TIMESTAMP(timezone=True),
    )

    transaction: Transaction = Relationship(back_populates="transfer")
    from_account: Account = Relationship(
        back_populates="from_transfers",
        sa_relationship_kwargs={"foreign_keys": "[Transfer.from_account_id]"},
    )
    to_account: Account = Relationship(
        back_populates="to_transfers",
        sa_relationship_kwargs={"foreign_keys": "[Transfer.to_account_id]"},
    )


async def get_user_async(username: str, session: AsyncSession) -> Optional[User]:
    """Retrieve a user by username using async session."""
    statement = select(User).where(User.username == username)
    result = await session.execute(statement)
    return result.scalar_one_or_none()
