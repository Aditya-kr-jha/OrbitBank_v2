from fastapi import APIRouter, Depends  # Import Depends

# Import the specific routers from users.py
from app.api.users import registration_router, user_crud_router, protected_user_router

# Import routers from other modules
from app.api import (
    banks,
    branches,
    account_types,
    accounts,
    transactions,
    transfers,
)
from app.auth import get_current_active_user

api_router = APIRouter()

api_router.include_router(registration_router, prefix="/users", tags=["Users"])

auth_dependency = Depends(get_current_active_user)

api_router.include_router(
    protected_user_router,
    prefix="/users",
    tags=["Users"],
    dependencies=[auth_dependency],
)

# Include user CRUD routes with authentication
api_router.include_router(
    user_crud_router, prefix="/users", tags=["Users"], dependencies=[auth_dependency]
)


# Include all other model routers with the authentication dependency
api_router.include_router(
    banks.router, prefix="/banks", tags=["Banks"], dependencies=[auth_dependency]
)
api_router.include_router(
    branches.router,
    prefix="/branches",
    tags=["Branches"],
    dependencies=[auth_dependency],
)
api_router.include_router(
    account_types.router,
    prefix="/account-types",
    tags=["Account Types"],
    dependencies=[auth_dependency],
)
api_router.include_router(
    accounts.router,
    prefix="/accounts",
    tags=["Accounts"],
    dependencies=[auth_dependency],
)
api_router.include_router(
    transactions.router,
    prefix="/transactions",
    tags=["Transactions"],
    dependencies=[auth_dependency],
)
api_router.include_router(
    transfers.router,
    prefix="/transfers",
    tags=["Transfers"],
    dependencies=[auth_dependency],
)
