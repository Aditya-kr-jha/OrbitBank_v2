from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.crud import create_crud_router, CRUDBase
from app.models.models import User, Account

from sqlmodel import select

from app.schemas.schemas import UserCreate, UserRead, UserUpdate, UserPasswordChange, AccountRead

# Router setup
router = APIRouter()

# Generate CRUD routes
user_crud_router = create_crud_router(
    model=User,
    create_schema=UserCreate,
    read_schema=UserRead,
    update_schema=UserUpdate,
    prefix="",  # Empty prefix as we'll include this under /users in main router
    tags=["Users"],
    pk_type=int,
    get_session_dependency=Depends(get_async_session)
)
router.include_router(user_crud_router)


@router.post("/{user_id}/change-password", status_code=status.HTTP_204_NO_CONTENT, tags=["Users"])
async def change_user_password(
        user_id: int,
        password_data: UserPasswordChange,
        session: AsyncSession = Depends(get_async_session)
):
    """Change a user's password with proper verification."""
    from app.auth import verify_password, hash_password

    user_crud = CRUDBase[User, UserCreate, UserRead, UserUpdate, int](User)
    db_user = await user_crud.get(db_session=session, pk_id=user_id)

    if not db_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Verify current password using the auth module function
    if not verify_password(password_data.current_password, db_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect current password")

    # Hash and update new password using the auth module function
    db_user.hashed_password = hash_password(password_data.new_password)

    # Update password_changed_at timestamp
    from datetime import datetime, timezone
    db_user.password_changed_at = datetime.now(timezone.utc)

    try:
        session.add(db_user)
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error updating password: {e}")

    return None


@router.get("/{user_id}/accounts", response_model=List[AccountRead], tags=["Users"])
async def get_user_accounts(
        user_id: int,
        session: AsyncSession = Depends(get_async_session)
):
    """Retrieve all accounts for a specific user."""
    # First check if user exists
    user_crud = CRUDBase[User, UserCreate, UserRead, UserUpdate, int](User)
    db_user = await user_crud.get(db_session=session, pk_id=user_id)

    if not db_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Get accounts
    statement = select(Account).where(Account.owner_id == user_id)
    result = await session.execute(statement)
    accounts = result.scalars().all()

    return accounts