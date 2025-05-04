from datetime import datetime, timezone

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.crud import create_crud_router, CRUDBase


from sqlmodel import select

from app.models.models import Branch, Account
from app.schemas.schemas import BranchCreate, BranchRead, BranchUpdate, AccountRead

router = APIRouter()

# Generate CRUD routes (note: branch uses string PK)
branch_crud_router = create_crud_router(
    model=Branch,
    create_schema=BranchCreate,
    read_schema=BranchRead,
    update_schema=BranchUpdate,
    prefix="",
    tags=["Branches"],
    pk_type=str,
    get_session_dependency=Depends(get_async_session)
)
router.include_router(branch_crud_router)


# Custom endpoints
@router.get("/{ifsc_code}/accounts", response_model=List[AccountRead], tags=["Branches"])
async def get_branch_accounts(
        ifsc_code: str,
        session: AsyncSession = Depends(get_async_session)
):
    """Retrieve all accounts for a specific branch."""
    # Check if branch exists
    branch_crud = CRUDBase[Branch, BranchCreate, BranchRead, BranchUpdate, str](Branch)
    db_branch = await branch_crud.get(db_session=session, pk_id=ifsc_code)

    if not db_branch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")

    # Get accounts
    statement = select(Account).where(Account.branch_ifsc == ifsc_code)
    result = await session.execute(statement)
    accounts = result.scalars().all()

    return accounts