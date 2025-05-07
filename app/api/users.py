import logging
from typing import List, Any, Coroutine
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Body,
    BackgroundTasks,
    Request,
)
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError  # Import IntegrityError
from datetime import datetime, timezone

from app.db.session import get_async_session
from app.crud import create_crud_router, CRUDBase
from app.models.models import User, Account
from app.auth import (
    hash_password,
    verify_password,
    get_current_active_user,
    verify_verification_token,
)  # Import hash_password and verify_password
from sqlmodel import select

from app.schemas.schemas import (
    UserCreate,
    UserRead,
    UserUpdate,
    UserPasswordChange,
    AccountRead,
)
from app.models.models import User
from app.services.notification_service_ses import (
    send_verification_email_task,
    SimpleSESNotificationService,
    get_ses_service,
)

logger = logging.getLogger(__name__)

# --- Router for User Registration (Public) ---
registration_router = APIRouter()
protected_user_router = APIRouter()


@registration_router.get(
    "/verify-email/{token}",
    response_model=UserRead,
    name="verify_email",
    responses={
        200: {"description": "Email successfully verified"},
        400: {"description": "Invalid or expired verification token"},
        404: {"description": "User not found"},
        500: {"description": "Internal server error"},
    },
)
async def verify_email(
    token: str, session: AsyncSession = Depends(get_async_session)
) -> User:
    """
    Iternal use :
    After a user registers, the system emails them a link containing a one‑time token.
    Calling this endpoint with that token marks the user’s is_email_verified flag to true.
    """
    email = verify_verification_token(token)

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token.",
        )

    # Find the user by email using where() and scalar_one_or_none()
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        logger.warning(
            f"Valid verification token used but user with email {email} not found"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User associated with this token not found.",
        )

    if user.is_email_verified:
        logger.info(f"Email {email} is already verified")
        return user

    # Mark as verified
    user.is_email_verified = True
    user.updated_at = datetime.now(timezone.utc)

    try:
        session.add(user)
        await session.commit()
        await session.refresh(user)
        logger.info(f"Email successfully verified for user {email} (ID: {user.id})")
        return user
    except Exception as e:
        await session.rollback()
        logger.exception(f"Database error during email verification for {email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during email verification.",
        )


@protected_user_router.get("/me", response_model=UserRead, tags=["Users (Me)"])
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """
    Get current logged-in user's profile.
    """
    return current_user


@protected_user_router.put("/me", response_model=UserRead, tags=["Users (Me)"])
async def update_user_me(
    *,
    user_in: UserUpdate,  # Use UserUpdate, but filter fields
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user),
):
    """
    Update own user profile (excluding password, status, username, etc.).
    """
    update_data = user_in.model_dump(exclude_unset=True)
    # Fields that the user should NOT be able to update via this endpoint
    excluded_fields = {
        "id",
        "username",
        "hashed_password",
        "status",
        "password_changed_at",
        "created_at",
        "updated_at",
    }

    updated = False
    for field, value in update_data.items():
        if field not in excluded_fields and hasattr(current_user, field):
            setattr(current_user, field, value)
            updated = True

    if not updated:
        # No valid fields were provided for update
        return current_user  # Or raise 400 Bad Request

    # Set updated_at timestamp
    current_user.updated_at = datetime.now(timezone.utc)

    try:
        session.add(current_user)
        await session.commit()
        await session.refresh(current_user)
        return current_user
    except IntegrityError as e:
        await session.rollback()
        detail = "Update failed due to a conflict (e.g., email already in use)."
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
    except Exception as e:
        await session.rollback()
        # Log error e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating the profile.",
        )


@protected_user_router.get(
    "/me/accounts", response_model=List[AccountRead], tags=["Users (Me)"]
)
async def get_my_accounts(
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user),
):
    """
    Retrieve accounts owned by the current logged-in user.
    """
    statement = select(Account).where(Account.owner_id == current_user.id)
    result = await session.execute(statement)
    accounts = result.scalars().all()
    return accounts


@registration_router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    tags=["Users"],
)
async def register_user(
    *,
    user_in: UserCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    ses_service: SimpleSESNotificationService = Depends(get_ses_service),
):
    """
    Register a new user and trigger email verification.
    """
    # Check if user already exists
    existing_user_check = await session.execute(
        select(User).where(User.username == user_in.username)
    )
    if existing_user_check.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already registered",
        )

    # Hash the password before creating the user object
    hashed_pwd = hash_password(user_in.password)
    user_data = user_in.model_dump()
    user_data["hashed_password"] = hashed_pwd
    del user_data["password"]  # Remove plain password

    # Set email as not verified initially
    user_data["is_email_verified"] = False

    db_user = User(**user_data)  # Create User model instance

    try:
        session.add(db_user)
        await session.commit()
        await session.refresh(db_user)

        # Get base URL from request
        base_url = f"{request.base_url}"

        # Add email verification task to background tasks
        background_tasks.add_task(
            send_verification_email_task,
            user_email=db_user.email,
            full_name=db_user.full_name,
            base_url=str(base_url),
            ses_service=ses_service,
        )

        logger.info(
            f"User {db_user.username} registered successfully. Verification email scheduled."
        )
        return db_user
    except IntegrityError as e:
        await session.rollback()
        logger.error(
            f"IntegrityError during user registration: {e.orig}", exc_info=True
        )
        detail = "User registration failed due to a conflict."

        if hasattr(e, "orig") and e.orig:
            error_msg = str(e.orig).lower()
            if "email" in error_msg:
                detail = "Email already registered."
            elif "username" in error_msg:
                detail = "Username already registered."
            elif "phone_number" in error_msg:
                detail = "Phone number already registered."
            elif "pan_number" in error_msg:
                detail = "PAN number already registered."

        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
    except Exception as e:
        await session.rollback()
        logger.error(f"Error during user registration: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during user registration. Please try again later.",
        )


user_crud_router = create_crud_router(
    model=User,
    create_schema=UserCreate,
    read_schema=UserRead,
    update_schema=UserUpdate,
    prefix="",
    tags=["Users"],
    pk_type=int,
    get_session_dependency=Depends(get_async_session),
)


@protected_user_router.post(
    "/{user_id}/change-password", status_code=status.HTTP_204_NO_CONTENT, tags=["Users"]
)
async def change_user_password(
    user_id: int,
    password_data: UserPasswordChange,
    session: AsyncSession = Depends(get_async_session),
    # current_user: User = Depends(get_current_active_user) # Dependency added at router level in api.py
    # TODO: Add logic here to ensure user_id matches current_user.id or current_user is admin
):
    """Change a user's password with proper verification."""
    # Note: verify_password and hash_password are imported at the top

    user_crud = CRUDBase[User, UserCreate, UserRead, UserUpdate, int](User)
    db_user = await user_crud.get(db_session=session, pk_id=user_id)

    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Verify current password using the auth module function
    if not verify_password(password_data.current_password, db_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect current password"
        )

    # Hash and update new password using the auth module function
    db_user.hashed_password = hash_password(password_data.new_password)

    # Update password_changed_at timestamp
    db_user.password_changed_at = datetime.now(timezone.utc)

    try:
        session.add(db_user)
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating password: {e}",
        )

    return None


@protected_user_router.get(
    "/{user_id}/accounts", response_model=List[AccountRead], tags=["Users"]
)
async def get_user_accounts(
    user_id: int,
    session: AsyncSession = Depends(get_async_session),
    # current_user: User = Depends(get_current_active_user) # Dependency added at router level in api.py
    # TODO: Add logic here to ensure user_id matches current_user.id or current_user is admin
):
    """Retrieve all accounts for a specific user."""
    # First check if user exists
    user_crud = CRUDBase[User, UserCreate, UserRead, UserUpdate, int](User)
    db_user = await user_crud.get(db_session=session, pk_id=user_id)

    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Get accounts
    statement = select(Account).where(Account.owner_id == user_id)
    result = await session.execute(statement)
    accounts = result.scalars().all()

    return accounts


class BeneficiaryAddRequest(BaseModel):
    beneficiary_username: str


@protected_user_router.post(
    "/me/beneficiaries",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    tags=["Users (Me)"],
)
async def add_beneficiary(
    *,
    beneficiary_in: BeneficiaryAddRequest,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user),
):
    """
    Add another registered user as a beneficiary for the current user.
    Requires the 'beneficiaries' relationship defined via UserBeneficiaryLink.
    """
    if beneficiary_in.beneficiary_username == current_user.username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot add yourself as a beneficiary.",
        )

    # Find the user to add as a beneficiary
    beneficiary_user_statement = select(User).where(
        User.username == beneficiary_in.beneficiary_username
    )
    result = await session.execute(beneficiary_user_statement)
    beneficiary_user = result.scalar_one_or_none()

    if not beneficiary_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{beneficiary_in.beneficiary_username}' not found.",
        )

    # Explicitly load the beneficiaries relationship
    try:
        await session.refresh(current_user, attribute_names=["beneficiaries"])
    except Exception as e:  # Catch potential errors if relationship doesn't exist
        # Log error e
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Could not load beneficiaries relationship: {e}",
        )

    # Check if already a beneficiary after loading
    if beneficiary_user in current_user.beneficiaries:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a beneficiary.",
        )

    try:
        # Append the user object to the relationship list
        current_user.beneficiaries.append(beneficiary_user)
        session.add(current_user)  # Mark current_user as modified
        await session.commit()
        # Refresh the beneficiary user object to ensure its data is up-to-date if needed
        await session.refresh(beneficiary_user)
        return beneficiary_user
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a beneficiary (database constraint).",
        )
    except Exception as e:
        await session.rollback()
        # Consider logging the error e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while adding the beneficiary.",
        )


@protected_user_router.get(
    "/me/beneficiaries", response_model=List[UserRead], tags=["Users (Me)"]
)
async def list_beneficiaries(
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user),
):
    """
    List all beneficiaries for the current user.
    Requires the 'beneficiaries' relationship to be defined and loaded.
    """
    try:
        # Explicitly load the beneficiaries relationship
        await session.refresh(current_user, attribute_names=["beneficiaries"])
    except Exception as e:  # Catch potential errors if relationship doesn't exist
        # Log error e
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Could not load beneficiaries relationship: {e}",
        )
    return current_user.beneficiaries


@protected_user_router.get(
    "/me/beneficiaries/{beneficiary_id}", response_model=UserRead, tags=["Users (Me)"]
)
async def get_beneficiary(
    beneficiary_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user),
):
    """
    Retrieve details of a specific beneficiary linked to the current user.
    Requires the 'beneficiaries' relationship to be defined and loaded.
    """

    # Ensure the relationship is loaded
    await session.refresh(current_user, attribute_names=["beneficiaries"])

    # Find the specific beneficiary in the current user's loaded list
    found_beneficiary = None
    for ben in current_user.beneficiaries:
        if ben.id == beneficiary_id:
            found_beneficiary = ben
            break

    if not found_beneficiary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Beneficiary not found for this user.",
        )

    return found_beneficiary


@protected_user_router.delete(
    "/me/beneficiaries/{beneficiary_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Users (Me)"],
)
async def delete_beneficiary(
    beneficiary_id: int,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_active_user),
):
    """
    Remove a beneficiary link for the current user.
    Requires the 'beneficiaries' relationship to be defined.
    """

    beneficiary_user_statement = select(User).where(User.id == beneficiary_id)
    result = await session.execute(beneficiary_user_statement)
    beneficiary_user = result.scalar_one_or_none()

    if not beneficiary_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Beneficiary user to remove not found in the system.",
        )

    # Ensure the relationship is loaded before attempting removal
    await session.refresh(current_user, attribute_names=["beneficiaries"])

    # Check if the user is actually in the current user's beneficiary list
    if beneficiary_user not in current_user.beneficiaries:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This user is not currently a beneficiary of the logged-in user.",
        )

    try:
        # Remove the user object from the relationship list
        current_user.beneficiaries.remove(beneficiary_user)
        session.add(current_user)  # Mark current_user as modified
        await session.commit()
    except Exception as e:
        await session.rollback()
        # Consider logging the error e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while removing the beneficiary.",
        )

    return None
