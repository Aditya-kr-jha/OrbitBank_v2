from datetime import datetime, timezone

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.crud import create_crud_router, CRUDBase


from sqlmodel import select

from app.model_enums.model_enums import TransactionType, TransactionStatus
from app.models.models import Transfer, Account, Transaction, Entry
from app.schemas.schemas import TransferCreate, TransferRead, TransferUpdate, NewTransferRequest

router = APIRouter()

# Generate CRUD routes
transfer_crud_router = create_crud_router(
    model=Transfer,
    create_schema=TransferCreate,
    read_schema=TransferRead,
    update_schema=TransferUpdate,
    prefix="",
    tags=["Transfers"],
    pk_type=int,
    get_session_dependency=Depends(get_async_session)
)
router.include_router(transfer_crud_router)


# Custom endpoints
@router.post("/new", response_model=TransferRead, tags=["Transfers"])
async def create_new_transfer(
        transfer_data: NewTransferRequest,
        session: AsyncSession = Depends(get_async_session)
):
    """Create a new transfer between accounts with all associated records."""
    # Check if accounts exist and get them
    from_account = await session.get(Account, transfer_data.from_account_id)
    to_account = await session.get(Account, transfer_data.to_account_id)

    if not from_account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Source account {transfer_data.from_account_id} not found")
    if not to_account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Destination account {transfer_data.to_account_id} not found")

    # Check sufficient funds
    if from_account.balance < transfer_data.amount:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Insufficient funds in source account")

    # Check currencies match (or implement conversion)
    if from_account.currency_code != to_account.currency_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Transfers between different currencies not supported")

    # Create transaction record
    transaction = Transaction(
        type=TransactionType.TRANSFER,
        status=TransactionStatus.COMPLETED,
        description=transfer_data.description or f"Transfer from {from_account.account_number} to {to_account.account_number}",
        initiated_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc)
    )
    session.add(transaction)
    await session.flush()  # Get transaction ID

    # Create transfer record
    transfer = Transfer(
        transaction_id=transaction.id,
        from_account_id=transfer_data.from_account_id,
        to_account_id=transfer_data.to_account_id,
        amount=transfer_data.amount,
        currency_code=from_account.currency_code
    )
    session.add(transfer)

    # Create debit entry (negative amount)
    debit_entry = Entry(
        account_id=transfer_data.from_account_id,
        amount=-transfer_data.amount,
        currency_code=from_account.currency_code,
        transaction_id=transaction.id
    )
    session.add(debit_entry)

    # Create credit entry (positive amount)
    credit_entry = Entry(
        account_id=transfer_data.to_account_id,
        amount=transfer_data.amount,
        currency_code=to_account.currency_code,
        transaction_id=transaction.id
    )
    session.add(credit_entry)

    # Update account balances
    from_account.balance -= transfer_data.amount
    to_account.balance += transfer_data.amount

    try:
        await session.commit()
        await session.refresh(transfer)
        return transfer
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Error processing transfer: {e}")