import logging
import re
from threading import Lock
import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from app.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SimpleSNSNotificationService:
    """
    A service class to send SMS notifications using AWS SNS.
    Reads configuration from app.config.settings.
    Uses synchronous operations with simplified error handling.
    """

    def __init__(self):
        """
        Initializes the SNS client using configuration from settings.
        Sets client to None if initialization fails.
        """
        self.region = settings.AWS_DEFAULT_REGION
        access_key_id = settings.AWS_ACCESS_KEY_ID
        secret_access_key = settings.AWS_SECRET_ACCESS_KEY

        if not all([self.region, access_key_id, secret_access_key]):
            logger.error("AWS SNS configuration (region, keys) is incomplete.")
            self.sns_client = None
            return

        try:
            self.sns_client = boto3.client(
                "sns",
                region_name=self.region,
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
            )
            logger.info(
                f"SimpleSNSNotificationService initialized in region: {self.region}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize AWS SNS client: {e}")
            self.sns_client = None

    def _validate_phone_number(self, phone_number: str) -> bool:
        """Validates phone number in E.164 format."""
        pattern = r"^\+[1-9]\d{1,14}$"
        if re.fullmatch(pattern, phone_number):
            return True
        logger.warning(
            f"Invalid phone number format: {phone_number}. Must be E.164 (e.g., +12223334444)."
        )
        return False

    def send_sms(self, phone_number: str, message: str) -> bool:
        """
        Sends an SMS using AWS SNS (synchronously).

        Args:
            phone_number: Recipient's phone number in E.164 format.
            message: SMS content (max 1600 bytes).

        Returns:
            True if SMS was sent successfully, False otherwise.
        """
        if not self.sns_client:
            logger.error("SNS client not initialized. Cannot send SMS.")
            return False
        if not phone_number or not self._validate_phone_number(phone_number):
            logger.warning("Invalid or missing phone number.")
            return False
        if not message:
            logger.warning("SMS message is empty.")
            return False
        if len(message.encode("utf-8")) > 1600:
            logger.warning(f"SMS message too long ({len(message)} chars).")

        try:
            response = self.sns_client.publish(
                PhoneNumber=phone_number,
                Message=message,
                MessageAttributes={
                    "AWS.SNS.SMS.SMSType": {
                        "DataType": "String",
                        "StringValue": "Transactional",
                    }
                },
            )
            logger.info(
                f"SMS sent to {phone_number}. Message ID: {response.get('MessageId')}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send SMS to {phone_number}: {e}")
            return False

    def add_phone_number_to_sandbox(self, phone_number: str) -> bool:
        """
        Initiates adding a phone number to the SNS SMS sandbox.

        Args:
            phone_number: Phone number in E.164 format.

        Returns:
            True if request was successful, False otherwise.
        """
        if not self.sns_client:
            logger.error("SNS client not initialized. Cannot add sandbox number.")
            return False
        if not phone_number or not self._validate_phone_number(phone_number):
            logger.warning("Invalid or missing phone number.")
            return False

        try:
            self.sns_client.create_sms_sandbox_phone_number(
                PhoneNumber=phone_number, LanguageCode="en-US"
            )
            logger.info(f"SNS sandbox verification initiated for {phone_number}")
            return True
        except Exception as e:
            logger.error(
                f"Failed to initiate SNS sandbox verification for {phone_number}: {e}"
            )
            return False


class SNSNotificationSingleton:
    _instance = None
    _lock = Lock()

    @classmethod
    def get_instance(cls) -> SimpleSNSNotificationService:
        """
        Returns the singleton instance of SimpleSNSNotificationService.
        Thread-safe initialization.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    logger.info(
                        "Creating SimpleSNSNotificationService singleton instance."
                    )
                    cls._instance = SimpleSNSNotificationService()
        return cls._instance


def get_sns_service() -> SimpleSNSNotificationService:
    """
    FastAPI dependency to get the SNS notification service singleton.
    """
    service = SNSNotificationSingleton.get_instance()
    if service.sns_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AWS SNS service is unavailable due to initialization failure.",
        )
    return service


sns_router = APIRouter()


class VerifyPhoneRequest(BaseModel):
    phone_number: str = Field(
        ...,
        pattern=r"^\+[1-9]\d{1,14}$",
        description="Phone number in E.164 format (e.g., +12223334444)",
    )


@sns_router.post(
    "/initiate-sandbox-phone-verification",
    status_code=status.HTTP_202_ACCEPTED,
    tags=["AWS SNS Utilities"],
    summary="Initiate SNS SMS Sandbox Phone Number Verification",
)
async def initiate_sandbox_phone_verification(
    request_body: VerifyPhoneRequest,
    sns_service: SimpleSNSNotificationService = Depends(get_sns_service),
):
    """
    Initiates AWS SNS phone number verification for the SMS sandbox.
    Users must provide the received OTP to complete verification via AWS Console/API.

    Args:
        request_body: Phone number in format.
        sns_service: Injected SNS service instance.

    Returns:
        Confirmation message.

    Raises:
        HTTPException 400: Invalid phone number format (via Pydantic).
        HTTPException 500: Failed to initiate verification.
    """
    if not sns_service.add_phone_number_to_sandbox(request_body.phone_number):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate SNS sandbox verification for {request_body.phone_number}.",
        )
    return {
        "message": "SNS sandbox verification initiated. User must provide the OTP via AWS Console/API."
    }
