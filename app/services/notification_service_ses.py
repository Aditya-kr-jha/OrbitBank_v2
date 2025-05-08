from threading import Lock

import boto3
import logging
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, status, HTTPException
from pydantic import BaseModel, EmailStr

from app.config import settings
from app.auth import create_verification_token, ACCESS_TOKEN_EXPIRE_MINUTES

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SimpleSESNotificationService:
    """
    A simpler service class to send email notifications using AWS SES.
    Reads configuration directly from the application settings.
    Uses synchronous operations.
    """

    def __init__(self):
        """
        Initializes the SES client using configuration from app.config.settings.
        """
        self.region = settings.AWS_DEFAULT_REGION
        self.sender_email = settings.SENDER_EMAIL
        access_key_id = settings.AWS_ACCESS_KEY_ID
        secret_access_key = settings.AWS_SECRET_ACCESS_KEY

        if not all([self.region, access_key_id, secret_access_key, self.sender_email]):
            logger.error(
                "AWS SES configuration (region, keys, sender email) is incomplete in settings."
            )
            raise ValueError("AWS SES configuration is incomplete.")

        try:
            # Create the boto3 client
            self.ses_client = boto3.client(
                "ses",
                region_name=self.region,
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
            )
            logger.info(
                f"SimpleSESNotificationService initialized for sender: {self.sender_email} in region: {self.region}"
            )
        except Exception as e:
            logger.exception("Failed to initialize AWS SES client.")
            raise RuntimeError(f"Failed to initialize AWS SES client: {e}") from e

    def send_email(self, recipient_email: str, subject: str, body_text: str) -> bool:
        """
        Sends an email using AWS SES (synchronously).

        Args:
            recipient_email: The email address of the recipient.
            subject: The subject line of the email.
            body_text: The plain text content of the email body.

        Returns:
            True if the email was sent successfully, False otherwise.
        """
        if not recipient_email:
            logger.warning("Recipient email address is missing. Cannot send email.")
            return False

        charset = "UTF-8"
        try:
            response = self.ses_client.send_email(
                Source=self.sender_email,
                Destination={"ToAddresses": [recipient_email]},
                Message={
                    "Subject": {"Data": subject, "Charset": charset},
                    "Body": {"Text": {"Data": body_text, "Charset": charset}},
                },
            )
            message_id = response.get("MessageId")
            logger.info(
                f"Email sent successfully to {recipient_email}. Message ID: {message_id}"
            )
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(
                f"Failed to send email to {recipient_email}: {error_code} - {error_message}"
            )
            return False
        except Exception as e:
            logger.exception(
                f"An unexpected error occurred while sending email to {recipient_email}: {e}"
            )
            return False


# --- Dependency Function ---
# Singleton instance to avoid re-initializing the client constantly
class SESNotificationSingleton:
    _instance = None
    _lock = Lock()

    @classmethod
    def get_instance(cls) -> SimpleSESNotificationService:
        """
        Returns the singleton instance of SimpleSESNotificationService.
        Thread-safe initialization.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    logger.info(
                        "Creating SimpleSESNotificationService singleton instance."
                    )
                    cls._instance = SimpleSESNotificationService()
        return cls._instance


# FastAPI dependency
def get_ses_service() -> SimpleSESNotificationService:
    """
    FastAPI dependency to get the SES notification service singleton.
    """
    return SESNotificationSingleton.get_instance()


# --- Router for SES Actions ---
ses_router = APIRouter()


def send_verification_email_task(
    user_email: str,
    full_name: str | None,
    base_url: str,
    ses_service: SimpleSESNotificationService,
):
    """
    Generates token and sends the verification email.
    Designed to be run as a background task.
    """
    try:
        token = create_verification_token(user_email)
        verification_url = f"{base_url}users/verify-email/{token}"

        logger.info(f"Generated verification URL for {user_email}: {verification_url}")

        subject = "OrbitBank: Please Verify Your Email Address"
        body = f"""
Hi {full_name or 'there'},

Thanks for registering with OrbitBank!

Please click the link below to verify your email address and activate your account:

{verification_url}

This link will expire in {ACCESS_TOKEN_EXPIRE_MINUTES // 60} hours.

If you did not register for this account, please ignore this email.

Thanks,
The OrbitBank Team
"""
        # Use the passed SES service instance to send
        sent = ses_service.send_email(
            recipient_email=user_email, subject=subject, body_text=body
        )
        if sent:
            logger.info(f"Verification email successfully sent to {user_email}.")
        else:
            logger.error(
                f"Failed to send verification email to {user_email} using SES service."
            )

    except Exception as e:
        # Log any error during background task execution
        logger.exception(
            f"Error in background task send_verification_email_task for {user_email}: {e}"
        )


class VerifyEmailRequest(BaseModel):
    email: EmailStr


@ses_router.post(
    "/verify-email-identity",
    status_code=status.HTTP_202_ACCEPTED,
    tags=["AWS SES"],
    summary="Request SES Email Verification (Sandbox Workaround)",
)
async def request_ses_email_verification(
    request_body: VerifyEmailRequest,
    ses_service: SimpleSESNotificationService = Depends(get_ses_service),
):
    """
    **SANDBOX USE ONLY.** Initiates AWS SES email verification for an address.

    Workaround for SES sandbox: allows sending *to* this address once the user
    manually clicks the verification link sent by AWS.
    This endpoint only triggers the AWS process; it does not auto-verify.
    Not for production .

    Args:
        request_body: Email address to verify.
        ses_service: SES notification service instance.

    Returns:
        Confirmation that the SES verification email request was initiated.

    Raises:
        HTTPException 503: SES service unavailable.
        HTTPException 500: AWS SES failed to process the request.
    """
    success = ses_service.ses_client.verify_email_identity(
        EmailAddress=request_body.email
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate SES email verification process for {request_body.email}. Check logs.",
        )

    return {
        "message": "SES verification email request initiated. The user must click the link in the email received from AWS to complete verification."
    }
