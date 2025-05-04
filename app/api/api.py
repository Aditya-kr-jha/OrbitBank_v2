from fastapi import APIRouter

from app.api import (
    users,
    banks,
    branches,
    account_types,
    accounts,
    transactions,
    transfers,
)

api_router = APIRouter()

# Include all model routers with their prefixes
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(banks.router, prefix="/banks", tags=["Banks"])
api_router.include_router(branches.router, prefix="/branches", tags=["Branches"])
api_router.include_router(account_types.router, prefix="/account-types", tags=["Account Types"])
api_router.include_router(accounts.router, prefix="/accounts", tags=["Accounts"])
api_router.include_router(transactions.router, prefix="/transactions", tags=["Transactions"])
api_router.include_router(transfers.router, prefix="/transfers", tags=["Transfers"])