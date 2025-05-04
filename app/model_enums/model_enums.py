from enum import Enum

class UserStatus(str, Enum):
    """User account status values."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"
    DELETED = "DELETED"


class AccountStatus(str, Enum):
    """Bank account status values."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    CLOSED = "CLOSED"
    FROZEN = "FROZEN"


class TransactionType(str, Enum):
    """Types of financial transactions."""
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    TRANSFER = "TRANSFER"
    PAYMENT = "PAYMENT"
    FEE = "FEE"
    INTEREST = "INTEREST"


class TransactionStatus(str, Enum):
    """Status values for transactions."""
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"
    PROCESSING = "PROCESSING"


class CurrencyCode(str, Enum):
    """Common ISO 4217 currency codes."""
    INR = "INR"  # Indian Rupee
    USD = "USD"  # US Dollar
    EUR = "EUR"  # Euro
    GBP = "GBP"  # British Pound
    JPY = "JPY"  # Japanese Yen
    AUD = "AUD"  # Australian Dollar
    CAD = "CAD"  # Canadian Dollar
    SGD = "SGD"  # Singapore Dollar
    CHF = "CHF"  # Swiss Franc
    CNY = "CNY"  # Chinese Yuan