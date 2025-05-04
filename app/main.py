import logging
from contextlib import asynccontextmanager
from datetime import timedelta

import uvicorn
from fastapi import (
    FastAPI,
    HTTPException,
    Depends,
    status,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.api import api_router
from app.auth import create_access_token, authenticate_user
from app.config import settings
from app.db.session import create_db_and_tables_async, get_async_session
from app.schemas.token import Token


logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting up the FastAPI application...")
    # Now we can directly call the async function without threadpool
    await create_db_and_tables_async()
    yield
    print("Shutting down the FastAPI application...")


app = FastAPI(lifespan=lifespan, title="Bank Application", version="0.1.2")

app.include_router(api_router)

@app.get("/")
async def root():
    return {"message": "Welcome to the OrbitBank API"}

@app.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_async_session),
):
    """Handles user login and returns JWT access token."""
    # We can directly await the async authentication function
    user = await authenticate_user(form_data.username, form_data.password, session)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


if __name__ == "__main__":
    # Use reload=True for development, remove for production
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)