from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.crud import create_crud_router, CRUDBase


from sqlmodel import select

from app.models.models import Transaction, Entry
from app.schemas.schemas import TransactionCreate, TransactionRead, TransactionUpdate, EntryRead

router = APIRouter()

# Generate CRUD routes
transaction_crud_router = create_crud_router(
    model=Transaction,
    create_schema=TransactionCreate,
    read_schema=TransactionRead,
    update_schema=TransactionUpdate,
    prefix="",
    tags=["Transactions"],
    pk_type=int,
    get_session_dependency=Depends(get_async_session)
)
router.include_router(transaction_crud_router)


# Custom endpoints
@router.get("/{transaction_id}/entries", response_model=List[EntryRead], tags=["Transactions"])
async def get_transaction_entries(
        transaction_id: int,
        session: AsyncSession = Depends(get_async_session)
):
    """Retrieve all entries associated with a transaction."""
    # Check if transaction exists
    transaction_crud = CRUDBase[Transaction, TransactionCreate, TransactionRead, TransactionUpdate, int](Transaction)
    db_transaction = await transaction_crud.get(db_session=session, pk_id=transaction_id)

    if not db_transaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")

    # Get entries
    statement = select(Entry).where(Entry.transaction_id == transaction_id)
    result = await session.execute(statement)
    entries = result.scalars().all()

    return entries