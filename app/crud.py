"""
Generic CRUD utilities for FastAPI using async SQLModel/SQLAlchemy.

This module provides:
- A base CRUD class for common database operations
- A factory function to create standard REST endpoints
"""
import logging
from typing import TypeVar, Generic, Type, List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlmodel import SQLModel, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from sqlalchemy import inspect

try:
    from app.db.session import get_async_session
except ImportError:
    logging.error("Could not import get_async_session from database")


    async def get_async_session():
        raise NotImplementedError("Database session dependency not configured")

# Generic type variables
ModelType = TypeVar("ModelType", bound=SQLModel)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
ReadSchemaType = TypeVar("ReadSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)
PrimaryKeyType = TypeVar("PrimaryKeyType", int, str)


class CRUDBase(Generic[ModelType, CreateSchemaType, ReadSchemaType, UpdateSchemaType, PrimaryKeyType]):
    """Base class for CRUD operations on SQLModel models using async SQLAlchemy."""

    def __init__(self, model: Type[ModelType]):
        """Initialize with a SQLModel class."""
        self.model = model
        try:
            mapper = inspect(self.model)
            if mapper is None:
                raise ValueError(f"Could not inspect model {self.model.__name__}")

            primary_key_columns = mapper.primary_key
            if not primary_key_columns:
                raise ValueError(f"No primary key found for model {self.model.__name__}")

            if len(primary_key_columns) > 1:
                pk_names = [c.name for c in primary_key_columns]
                raise NotImplementedError(
                    f"Composite primary keys ({pk_names}) not supported for {self.model.__name__}"
                )

            self.pk_column = primary_key_columns[0]
            self.pk_name = self.pk_column.name

        except Exception as e:
            logging.error(f"Failed to determine primary key for {self.model.__name__}: {e}")
            raise RuntimeError(f"Failed to initialize CRUD for {self.model.__name__}: {e}") from e

    async def get(self, db_session: AsyncSession, pk_id: PrimaryKeyType) -> Optional[ModelType]:
        """Get a single record by primary key."""
        statement = select(self.model).where(self.pk_column == pk_id)
        result = await db_session.execute(statement)
        return result.scalar_one_or_none()

    async def get_multi(
            self, db_session: AsyncSession, *, skip: int = 0, limit: int = 100
    ) -> List[ModelType]:
        """Get multiple records with pagination."""
        statement = select(self.model).offset(skip).limit(limit)
        result = await db_session.execute(statement)
        return result.scalars().all()

    async def create(self, db_session: AsyncSession, *, obj_in: CreateSchemaType) -> ModelType:
        """Create a new record."""
        db_obj = self.model.model_validate(obj_in)
        try:
            db_session.add(db_obj)
            await db_session.commit()
            await db_session.refresh(db_obj)
            return db_obj
        except IntegrityError as e:
            await db_session.rollback()
            logging.warning(f"Integrity error creating {self.model.__name__}: {e.orig}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Database integrity error: {e.orig}"
            )
        except Exception as e:
            await db_session.rollback()
            logging.error(f"Error creating {self.model.__name__}: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error creating item")

    async def update(
            self, db_session: AsyncSession, *, pk_id: PrimaryKeyType, obj_in: UpdateSchemaType
    ) -> Optional[ModelType]:
        """Update an existing record."""
        db_obj = await self.get(db_session=db_session, pk_id=pk_id)
        if not db_obj:
            return None

        update_data = obj_in.model_dump(exclude_unset=True)
        if not update_data:
            return db_obj

        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
            else:
                logging.warning(f"Field '{field}' doesn't exist on {self.model.__name__}")

        try:
            db_session.add(db_obj)
            await db_session.commit()
            await db_session.refresh(db_obj)
            return db_obj
        except IntegrityError as e:
            await db_session.rollback()
            logging.warning(f"Integrity error updating {self.model.__name__} (ID: {pk_id}): {e.orig}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Database integrity error: {e.orig}"
            )
        except Exception as e:
            await db_session.rollback()
            logging.error(f"Error updating {self.model.__name__} (ID: {pk_id}): {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error updating item")

    async def remove(self, db_session: AsyncSession, *, pk_id: PrimaryKeyType) -> Optional[ModelType]:
        """Delete a record by primary key."""
        db_obj = await self.get(db_session=db_session, pk_id=pk_id)
        if not db_obj:
            return None

        try:
            await db_session.delete(db_obj)
            await db_session.commit()
            return db_obj
        except IntegrityError as e:
            await db_session.rollback()
            logging.warning(f"Integrity error deleting {self.model.__name__} (ID: {pk_id}): {e.orig}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot delete due to existing references: {e.orig}"
            )
        except Exception as e:
            await db_session.rollback()
            logging.error(f"Error deleting {self.model.__name__} (ID: {pk_id}): {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error deleting item")


def create_crud_router(
        *,
        model: Type[ModelType],
        create_schema: Type[CreateSchemaType],
        read_schema: Type[ReadSchemaType],
        update_schema: Type[UpdateSchemaType],
        prefix: str,
        tags: List[str],
        pk_type: Type[PrimaryKeyType]=int,
        get_session_dependency: Any = Depends(get_async_session)
) -> APIRouter:
    """Create a FastAPI router with standard CRUD endpoints."""
    router = APIRouter(prefix=prefix, tags=tags)
    crud = CRUDBase[ModelType, CreateSchemaType, ReadSchemaType, UpdateSchemaType, pk_type](model)

    @router.post("/", response_model=read_schema, status_code=status.HTTP_201_CREATED)
    async def create_item(
            *,
            item_in: create_schema,
            session: AsyncSession = get_session_dependency
    ):
        """Create a new item."""
        return await crud.create(db_session=session, obj_in=item_in)

    @router.get("/", response_model=List[read_schema])
    async def read_items(
            *,
            skip: int = Query(0, ge=0, description="Number of items to skip"),
            limit: int = Query(100, ge=1, le=200, description="Max items to return"),
            session: AsyncSession = get_session_dependency
    ):
        """Retrieve multiple items."""
        return await crud.get_multi(db_session=session, skip=skip, limit=limit)

    @router.get("/{item_id}", response_model=read_schema)
    async def read_item(
            *,
            item_id: pk_type,
            session: AsyncSession = get_session_dependency
    ):
        """Retrieve a single item by its primary key."""
        item = await crud.get(db_session=session, pk_id=item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{model.__name__} with {crud.pk_name} '{item_id}' not found"
            )
        return item

    @router.put("/{item_id}", response_model=read_schema)
    async def update_item(
            *,
            item_id: pk_type,
            item_in: update_schema,
            session: AsyncSession = get_session_dependency
    ):
        """Update an existing item."""
        updated_item = await crud.update(db_session=session, pk_id=item_id, obj_in=item_in)
        if updated_item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{model.__name__} with {crud.pk_name} '{item_id}' not found"
            )
        return updated_item

    @router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_item(
            *,
            item_id: pk_type,
            session: AsyncSession = get_session_dependency
    ):
        """Delete an item."""
        deleted_item = await crud.remove(db_session=session, pk_id=item_id)
        if deleted_item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{model.__name__} with {crud.pk_name} '{item_id}' not found"
            )
        return None

    return router