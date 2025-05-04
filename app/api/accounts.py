from datetime import datetime, timezone

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.crud import create_crud_router, CRUDBase


from sqlmodel import select

from app.model_enums.model_enums import TransactionType, TransactionStatus
from app.models.models import Account, Entry, Transaction
from app.schemas.schemas import AccountCreate, AccountRead, AccountUpdate, EntryRead, TransactionRead, DepositRequest

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
    get_session_dependency=Depends(get_async_session)
)
router.include_router(account_crud_router)


# Custom endpoints
@router.get("/{account_id}/entries", response_model=List[EntryRead], tags=["Accounts"])
async def get_account_entries(
        account_id: int,
        session: AsyncSession = Depends(get_async_session)
):
    """Retrieve all accounting entries for a specific account."""
    # Check if account exists
    account_crud = CRUDBase[Account, AccountCreate, AccountRead, AccountUpdate, int](Account)
    db_account = await account_crud.get(db_session=session, pk_id=account_id)

    if not db_account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    # Get entries
    statement = select(Entry).where(Entry.account_id == account_id)
    result = await session.execute(statement)
    entries = result.scalars().all()

    return entries


@router.post("/{account_id}/deposit", response_model=TransactionRead, tags=["Accounts"])
async def deposit_to_account(
        account_id: int,
        deposit_data: DepositRequest,
        session: AsyncSession = Depends(get_async_session)
):
    """Deposit funds into an account."""
    # Check if account exists and get account
    account_crud = CRUDBase[Account, AccountCreate, AccountRead, AccountUpdate, int](Account)
    db_account = await account_crud.get(db_session=session, pk_id=account_id)

    if not db_account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    # Create transaction record
    transaction = Transaction(
        type=TransactionType.DEPOSIT,
        status=TransactionStatus.COMPLETED,
        description=deposit_data.description or f"Deposit to account {db_account.account_number}",
        initiated_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc)
    )
    session.add(transaction)
    await session.flush()  # Get transaction ID

    # Create entry record
    entry = Entry(
        account_id=account_id,
        amount=deposit_data.amount,
        currency_code=db_account.currency_code,
        transaction_id=transaction.id
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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Error processing deposit: {e}")