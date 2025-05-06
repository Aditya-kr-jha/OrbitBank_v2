import logging
from datetime import datetime, timezone

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Body, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_async_session
from app.crud import create_crud_router, CRUDBase


from sqlmodel import select

from app.model_enums.model_enums import TransactionType, TransactionStatus
from app.models.models import Transfer, Account, Transaction, Entry
from app.schemas.schemas import (
    TransferCreate,
    TransferRead,
    TransferUpdate,
    NewTransferRequest,
)
from services.notification_service_ses import (
    get_ses_service,
    SimpleSESNotificationService,
)
from app.services.notification_service_sns import (
    SimpleSNSNotificationService as SNSService,
    get_sns_service,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

router = APIRouter()

# Generate CRUD routes
transfer_crud_router = create_crud_router(
    model=Transfer,
    create_schema=TransferCreate,
    read_schema=TransferRead,
    update_schema=TransferUpdate,
    prefix="",
    tags=["Transfers"],
    pk_type=int,
    get_session_dependency=Depends(get_async_session),
)
router.include_router(transfer_crud_router)


# Custom endpoints
@router.post("/new", response_model=TransferRead, tags=["Transfers"])
async def create_new_transfer(
    transfer_data: NewTransferRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_async_session),
    ses_service: SimpleSESNotificationService = Depends(get_ses_service),
    sns_service: SNSService = Depends(get_sns_service),  # Add SNS Service dependency
):
    """
    Create a new transfer between accounts, update balances, create records,
    and send email and SMS notifications to both parties involved.
    """
    # Fetch accounts with their owners eagerly loaded
    from_account_stmt = (
        select(Account)
        .options(selectinload(Account.owner))
        .where(Account.id == transfer_data.from_account_id)
    )
    to_account_stmt = (
        select(Account)
        .options(selectinload(Account.owner))
        .where(Account.id == transfer_data.to_account_id)
    )

    from_account_res = await session.execute(from_account_stmt)
    from_account: Account | None = from_account_res.scalar_one_or_none()

    to_account_res = await session.execute(to_account_stmt)
    to_account: Account | None = to_account_res.scalar_one_or_none()

    if not from_account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source account {transfer_data.from_account_id} not found",
        )
    if not to_account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Destination account {transfer_data.to_account_id} not found",
        )

    # --- Validation Checks ---
    if from_account.balance < transfer_data.amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient funds in source account",
        )

    if from_account.currency_code != to_account.currency_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transfers between different currencies not currently supported",
        )
    # --- End Validation Checks ---

    # --- Database Operations ---
    now = datetime.now(timezone.utc)
    transaction = Transaction(
        type=TransactionType.TRANSFER,
        status=TransactionStatus.PENDING,
        description=transfer_data.description
        or f"Transfer from {from_account.account_number} to {to_account.account_number}",
        initiated_at=now,
    )
    session.add(transaction)
    await session.flush()

    transfer = Transfer(
        transaction_id=transaction.id,
        from_account_id=transfer_data.from_account_id,
        to_account_id=transfer_data.to_account_id,
        amount=transfer_data.amount,
        currency_code=from_account.currency_code,
    )
    session.add(transfer)

    debit_entry = Entry(
        account_id=transfer_data.from_account_id,
        amount=-transfer_data.amount,
        currency_code=from_account.currency_code,
        transaction_id=transaction.id,
    )
    session.add(debit_entry)

    credit_entry = Entry(
        account_id=transfer_data.to_account_id,
        amount=transfer_data.amount,
        currency_code=to_account.currency_code,
        transaction_id=transaction.id,
    )
    session.add(credit_entry)

    from_account.balance -= transfer_data.amount
    to_account.balance += transfer_data.amount
    session.add(from_account)
    session.add(to_account)
    # --- End Database Operations ---

    try:
        transaction.status = TransactionStatus.COMPLETED
        transaction.completed_at = datetime.now(timezone.utc)
        session.add(transaction)

        await session.commit()
        await session.refresh(transfer)
        await session.refresh(from_account)
        await session.refresh(to_account)
        await session.refresh(transaction)

        # --- Send Notifications ---
        transfer_time_str = transaction.completed_at.strftime("%Y-%m-%d %H:%M:%S %Z")
        amount_str = f"{transfer_data.amount:.2f} {from_account.currency_code}"

        # 1. Notify Sender (Email and SMS)
        if from_account.owner:
            # Email Sender
            if from_account.owner.email:
                sender_subject = f"Transfer Sent Confirmation - Account {from_account.account_number}"
                sender_body = (
                    f"Dear {from_account.owner.full_name or 'Customer'},\n\n"
                    f"You have successfully transferred {amount_str} "
                    f"from your account ({from_account.account_number}) "
                    f"to account {to_account.account_number} "
                    f"on {transfer_time_str}.\n\n"
                    f"Description: {transaction.description}\n"
                    f"Transaction ID: {transaction.id}\n"
                    f"Your new balance is: {from_account.balance:.2f} {from_account.currency_code}\n\n"
                    f"Thank you for banking with us."
                )
                background_tasks.add_task(
                    ses_service.send_email,
                    recipient_email=from_account.owner.email,
                    subject=sender_subject,
                    body_text=sender_body,
                )
                logger.info(
                    f"Transfer SENT email notification queued for account {from_account.id} to {from_account.owner.email}"
                )
            else:
                logger.warning(
                    f"Could not send transfer SENT email notification for account {from_account.id}: Email missing."
                )

            # SMS Sender
            if from_account.owner.phone_number:
                if sns_service._validate_phone_number(from_account.owner.phone_number):
                    sender_sms = (
                        f"Transfer Sent: -{amount_str} "
                        f"from Acct ...{from_account.account_number[-4:]} "
                        f"to Acct ...{to_account.account_number[-4:]}. "
                        f"New Bal: {from_account.balance:.2f} {from_account.currency_code}. "
                        f"TxID: {transaction.id}"
                    )
                    background_tasks.add_task(
                        sns_service.send_sms,
                        phone_number=from_account.owner.phone_number,
                        message=sender_sms,
                    )
                    logger.info(
                        f"Transfer SENT SMS notification queued for account {from_account.id} to {from_account.owner.phone_number}"
                    )
                else:
                    logger.warning(
                        f"Could not send transfer SENT SMS for account {from_account.id}: Invalid phone number format for {from_account.owner.phone_number}."
                    )
            else:
                logger.warning(
                    f"Could not send transfer SENT SMS notification for account {from_account.id}: Phone number missing."
                )
        else:
            logger.warning(
                f"Could not send transfer SENT notifications for account {from_account.id}: Owner missing."
            )

        # 2. Notify Receiver (Email and SMS)
        if to_account.owner:
            # Email Receiver
            if to_account.owner.email:
                receiver_subject = (
                    f"Incoming Transfer Received - Account {to_account.account_number}"
                )
                receiver_body = (
                    f"Dear {to_account.owner.full_name or 'Customer'},\n\n"
                    f"You have received an incoming transfer of {amount_str} "
                    f"into your account ({to_account.account_number}) "
                    f"from account {from_account.account_number} "
                    f"on {transfer_time_str}.\n\n"
                    f"Description: {transaction.description}\n"
                    f"Transaction ID: {transaction.id}\n"
                    f"Your new balance is: {to_account.balance:.2f} {to_account.currency_code}\n\n"
                    f"Thank you for banking with us."
                )
                background_tasks.add_task(
                    ses_service.send_email,
                    recipient_email=to_account.owner.email,
                    subject=receiver_subject,
                    body_text=receiver_body,
                )
                logger.info(
                    f"Transfer RECEIVED email notification queued for account {to_account.id} to {to_account.owner.email}"
                )
            else:
                logger.warning(
                    f"Could not send transfer RECEIVED email notification for account {to_account.id}: Email missing."
                )

            # SMS Receiver
            if to_account.owner.phone_number:
                if sns_service._validate_phone_number(to_account.owner.phone_number):
                    receiver_sms = (
                        f"Transfer Received: +{amount_str} "
                        f"to Acct ...{to_account.account_number[-4:]} "
                        f"from Acct ...{from_account.account_number[-4:]}. "
                        f"New Bal: {to_account.balance:.2f} {to_account.currency_code}. "
                        f"TxID: {transaction.id}"
                    )
                    background_tasks.add_task(
                        sns_service.send_sms,
                        phone_number=to_account.owner.phone_number,
                        message=receiver_sms,
                    )
                    logger.info(
                        f"Transfer RECEIVED SMS notification queued for account {to_account.id} to {to_account.owner.phone_number}"
                    )
                else:
                    logger.warning(
                        f"Could not send transfer RECEIVED SMS for account {to_account.id}: Invalid phone number format for {to_account.owner.phone_number}."
                    )
            else:
                logger.warning(
                    f"Could not send transfer RECEIVED SMS notification for account {to_account.id}: Phone number missing."
                )
        else:
            logger.warning(
                f"Could not send transfer RECEIVED notifications for account {to_account.id}: Owner missing."
            )
        # --- End Notifications ---

        return transfer

    except Exception as e:
        await session.rollback()
        logger.error(
            f"Error processing transfer from account {transfer_data.from_account_id} to {transfer_data.to_account_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing transfer: An internal error occurred.",
        )
