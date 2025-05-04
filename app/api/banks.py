from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.crud import create_crud_router, CRUDBase


from sqlmodel import select

from app.models.models import Bank, Branch
from app.schemas.schemas import BankCreate, BankRead, BankUpdate, BranchRead

router = APIRouter()

# Generate CRUD routes
bank_crud_router = create_crud_router(
    model=Bank,
    create_schema=BankCreate,
    read_schema=BankRead,
    update_schema=BankUpdate,
    prefix="",
    tags=["Banks"],
    pk_type=int,
    get_session_dependency=Depends(get_async_session)
)
router.include_router(bank_crud_router)


# Custom endpoints
@router.get("/{bank_id}/branches", response_model=List[BranchRead], tags=["Banks"])
async def get_bank_branches(
        bank_id: int,
        session: AsyncSession = Depends(get_async_session)
):
    """Retrieve all branches for a specific bank."""
    # Check if bank exists
    bank_crud = CRUDBase[Bank, BankCreate, BankRead, BankUpdate, int](Bank)
    db_bank = await bank_crud.get(db_session=session, pk_id=bank_id)

    if not db_bank:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bank not found")

    # Get branches
    statement = select(Branch).where(Branch.bank_id == bank_id)
    result = await session.execute(statement)
    branches = result.scalars().all()

    return branches