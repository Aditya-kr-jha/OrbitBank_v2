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
from sqlmodel import select, Session
from starlette.concurrency import run_in_threadpool



from app.auth import create_access_token, authenticate_user
from app.config import settings
from app.db.session import create_db_and_tables, get_session
from app.schemas.token import Token




logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting up the FastAPI application...")
    # This synchronous call might block if DB init is slow,threadpool is needed
    await run_in_threadpool(create_db_and_tables)
    yield
    print("Shutting down the FastAPI application...")


app = FastAPI(lifespan=lifespan, title="Bank Application", version="0.1.2")

@app.get("/")
async def root():
    return {"message": "Welcome to the OrbitBank API"}

@app.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),  # Ensure Session type hint is correct
):
    """Handles user login and returns JWT access token."""
    # --- Run synchronous authentication in threadpool ---
    user = await run_in_threadpool(
        authenticate_user, form_data.username, form_data.password, session
    )
    # --- End threadpool execution ---

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,  # Use status from fastapi
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