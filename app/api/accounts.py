from datetime import datetime, timezone, date

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Body, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.crud import create_crud_router, CRUDBase


from sqlmodel import select

from app.model_enums.model_enums import TransactionType, TransactionStatus
from app.models.models import Account, Entry, Transaction
from app.schemas.schemas import (
    AccountCreate,
    AccountRead,
    AccountUpdate,
    EntryRead,
    TransactionRead,
    DepositRequest,
    AccountBalanceRead,
    WithdrawalRequest,
)

router = APIRouter()

# Generate CRUD routes
account_crud_router = create_crud_router(
    model=Account,
    create_schema=AccountCreate,
    read_schema=AccountRead,
    update_schema=AccountUpdate,
    prefix="",
    tags=["Accounts"],
    pk_type=int,
    get_session_dependency=Depends(get_async_session),
)
router.include_router(account_crud_router)


# --- Helper Function to Get Account ---
async def get_account_or_404(account_id: int, session: AsyncSession) -> Account:
    """Gets an account by ID or raises HTTPException 404."""
    # Use session.get for direct primary key lookup
    db_account = await session.get(Account, account_id)
    if not db_account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account not found"
        )
    return db_account


@router.get(
    "/{account_id}/balance", response_model=AccountBalanceRead, tags=["Accounts"]
)
async def get_account_balance(
    account_id: int, session: AsyncSession = Depends(get_async_session)
):
    """Retrieve the current balance of a specific account."""
    db_account = await get_account_or_404(account_id, session)
    return AccountBalanceRead(
        balance=db_account.balance, account_number=db_account.account_number
    )


# Custom endpoints
@router.get("/{account_id}/entries", response_model=List[EntryRead], tags=["Accounts"])
async def get_account_entries(
    account_id: int, session: AsyncSession = Depends(get_async_session)
):
    """Retrieve all accounting entries for a specific account."""
    # Check if account exists
    account_crud = CRUDBase[Account, AccountCreate, AccountRead, AccountUpdate, int](
        Account
    )
    db_account = await account_crud.get(db_session=session, pk_id=account_id)

    if not db_account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account not found"
        )

    # Get entries
    statement = select(Entry).where(Entry.account_id == account_id)
    result = await session.execute(statement)
    entries = result.scalars().all()

    return entries


@router.post("/{account_id}/deposit", response_model=TransactionRead, tags=["Accounts"])
async def deposit_to_account(
    account_id: int,
    deposit_data: DepositRequest,
    session: AsyncSession = Depends(get_async_session),
):
    """Deposit funds into an account."""
    # Check if account exists and get account
    account_crud = CRUDBase[Account, AccountCreate, AccountRead, AccountUpdate, int](
        Account
    )
    db_account = await account_crud.get(db_session=session, pk_id=account_id)

    if not db_account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account not found"
        )

    # Create transaction record
    transaction = Transaction(
        type=TransactionType.DEPOSIT,
        status=TransactionStatus.COMPLETED,
        description=deposit_data.description
        or f"Deposit to account {db_account.account_number}",
        initiated_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    session.add(transaction)
    await session.flush()  # Get transaction ID

    # Create entry record
    entry = Entry(
        account_id=account_id,
        amount=deposit_data.amount,
        currency_code=db_account.currency_code,
        transaction_id=transaction.id,
    )
    session.add(entry)

    # Update account balance
    db_account.balance += deposit_data.amount
    session.add(db_account)

    try:
        await session.commit()
        await session.refresh(transaction)
        return transaction
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing deposit: {e}",
        )


@router.post(
    "/{account_id}/withdraw", response_model=TransactionRead, tags=["Accounts"]
)
async def withdraw_from_account(
    account_id: int,
    withdrawal_data: WithdrawalRequest,
    session: AsyncSession = Depends(get_async_session),
):
    """Withdraw funds from an account."""
    db_account = await get_account_or_404(account_id, session)

    # Check sufficient funds
    if db_account.balance < withdrawal_data.amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient funds"
        )

    # Create transaction record
    transaction = Transaction(
        type=TransactionType.WITHDRAWAL,
        status=TransactionStatus.COMPLETED,
        description=withdrawal_data.description
        or f"Withdrawal from account {db_account.account_number}",
        initiated_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    session.add(transaction)
    await session.flush()  # Get transaction ID

    # Create entry record (negative amount for withdrawal)
    entry = Entry(
        account_id=account_id,
        amount=-withdrawal_data.amount,  # Negative amount
        currency_code=db_account.currency_code,  # Use account's currency
        transaction_id=transaction.id,
    )
    session.add(entry)

    # Update account balance
    db_account.balance -= withdrawal_data.amount
    session.add(db_account)  # Mark account as dirty

    try:
        await session.commit()
        await session.refresh(transaction)
        return transaction
    except Exception as e:
        await session.rollback()
        # Log error e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing withdrawal: {e}",
        )


@router.get(
    "/{account_id}/statement", response_model=List[EntryRead], tags=["Accounts"]
)
async def get_account_statement(
    account_id: int,
    start_date_str: Optional[str] = Query(
        None,
        description="Filter entries from this date (YYYY-MM-DD)",
        alias="start_date",
        regex=r"^\d{4}-\d{2}-\d{2}$",
    ),
    end_date_str: Optional[str] = Query(
        None,
        description="Filter entries up to this date (YYYY-MM-DD)",
        alias="end_date",
        regex=r"^\d{4}-\d{2}-\d{2}$",
    ),
    skip: int = Query(0, ge=0, description="Number of entries to skip"),
    limit: int = Query(100, ge=1, le=200, description="Max entries to return"),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Retrieve a statement (list of entries) for an account, optionally filtered by date (YYYY-MM-DD).
    """
    await get_account_or_404(account_id, session)  # Check if account exists

    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None

    # Parse and validate date strings
    try:
        if start_date_str:
            start_datetime = datetime.combine(
                date.fromisoformat(start_date_str),
                datetime.min.time(),
                tzinfo=timezone.utc,
            )
        if end_date_str:
            # Include the whole end day
            end_datetime = datetime.combine(
                date.fromisoformat(end_date_str),
                datetime.max.time(),
                tzinfo=timezone.utc,
            )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD.",
        )

    # Base query for entries
    statement_query = select(Entry).where(Entry.account_id == account_id)

    # Apply date filters using Entry.created_at
    if start_datetime:
        statement_query = statement_query.where(Entry.created_at >= start_datetime)
    if end_datetime:
        statement_query = statement_query.where(Entry.created_at <= end_datetime)

    # Apply ordering by timestamp descending and pagination
    statement_query = statement_query.order_by(Entry.created_at.desc())
    statement_query = statement_query.offset(skip).limit(limit)

    result = await session.execute(statement_query)
    entries = result.scalars().all()

    return entries


@router.get(
    "/{account_id}/transactions",
    response_model=List[TransactionRead],
    tags=["Accounts"],
)
async def get_account_transactions(
    account_id: int,
    start_date_str: Optional[str] = Query(
        None,
        description="Filter transactions from this date (YYYY-MM-DD)",
        alias="start_date",
        regex=r"^\d{4}-\d{2}-\d{2}$",
    ),
    end_date_str: Optional[str] = Query(
        None,
        description="Filter transactions up to this date (YYYY-MM-DD)",
        alias="end_date",
        regex=r"^\d{4}-\d{2}-\d{2}$",
    ),
    transaction_type: Optional[TransactionType] = Query(
        None, description="Filter by transaction type"
    ),
    skip: int = Query(0, ge=0, description="Number of transactions to skip"),
    limit: int = Query(100, ge=1, le=200, description="Max transactions to return"),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Retrieve transaction history related to this account, optionally filtered by date (YYYY-MM-DD) and type.
    """
    await get_account_or_404(account_id, session)  # Check if account exists

    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None

    # Parse and validate date strings
    try:
        if start_date_str:
            start_datetime = datetime.combine(
                date.fromisoformat(start_date_str),
                datetime.min.time(),
                tzinfo=timezone.utc,
            )
        if end_date_str:
            # Include the whole end day
            end_datetime = datetime.combine(
                date.fromisoformat(end_date_str),
                datetime.max.time(),
                tzinfo=timezone.utc,
            )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD.",
        )

    # 1. Find transaction IDs related to this account via Entries
    entry_tx_ids_query = (
        select(Entry.transaction_id).where(Entry.account_id == account_id).distinct()
    )
    entry_tx_ids_result = await session.execute(entry_tx_ids_query)
    related_transaction_ids = entry_tx_ids_result.scalars().all()

    if not related_transaction_ids:
        return []  # No transactions found for this account

    # 2. Query Transactions using the found IDs and apply filters
    transaction_query = select(Transaction).where(
        Transaction.id.in_(related_transaction_ids)
    )

    # Apply date filters (using completed_at)
    # Ensure Transaction.completed_at is not None for comparison
    if start_datetime:
        transaction_query = transaction_query.where(
            Transaction.completed_at is not None,
            Transaction.completed_at >= start_datetime,
        )
    if end_datetime:
        transaction_query = transaction_query.where(
            Transaction.completed_at is not None,
            Transaction.completed_at <= end_datetime,
        )

    # Apply type filter
    if transaction_type:
        transaction_query = transaction_query.where(
            Transaction.type == transaction_type
        )

    # Apply ordering (e.g., by completion date descending, handle None values) and pagination
    # Place None completed_at dates last if ordering by descending
    transaction_query = transaction_query.order_by(
        Transaction.completed_at.desc().nullslast()
    )
    transaction_query = transaction_query.offset(skip).limit(limit)

    result = await session.execute(transaction_query)
    transactions = result.scalars().all()

    return transactions
