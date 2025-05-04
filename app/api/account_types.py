from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.crud import create_crud_router, CRUDBase


from sqlmodel import select

from app.models.models import AccountType, Account
from app.schemas.schemas import AccountTypeCreate, AccountTypeRead, AccountTypeUpdate, AccountRead

router = APIRouter()

# Generate CRUD routes (note: account type uses string PK)
account_type_crud_router = create_crud_router(
    model=AccountType,
    create_schema=AccountTypeCreate,
    read_schema=AccountTypeRead,
    update_schema=AccountTypeUpdate,
    prefix="",
    tags=["Account Types"],
    pk_type=str,  # Code is a string primary key
    get_session_dependency=Depends(get_async_session)
)
router.include_router(account_type_crud_router)


# Custom endpoints
@router.get("/{code}/accounts", response_model=List[AccountRead], tags=["Account Types"])
async def get_accounts_by_type(
        code: str,
        session: AsyncSession = Depends(get_async_session)
):
    """Retrieve all accounts of a specific account type."""
    # Check if account type exists
    account_type_crud = CRUDBase[AccountType, AccountTypeCreate, AccountTypeRead, AccountTypeUpdate, str](AccountType)
    db_account_type = await account_type_crud.get(db_session=session, pk_id=code)

    if not db_account_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account type not found")

    # Get accounts
    statement = select(Account).where(Account.account_type_code == code)
    result = await session.execute(statement)
    accounts = result.scalars().all()

    return accounts