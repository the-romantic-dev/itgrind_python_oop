from enum import Enum


class AccountStatus(Enum):
    ACTIVE = "Active"
    FROZEN = "Frozen"
    CLOSED = "Closed"

class Currency(Enum):
    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"
    KZT = "KZT"
    CNY = "CNY"

class ClientStatus(Enum):
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"


class TransactionType(Enum):
    DEPOSIT = "Deposit"
    WITHDRAW = "Withdraw"
    TRANSFER = "Transfer"
    EXTERNAL_TRANSFER = "External transfer"


class TransactionStatus(Enum):
    CREATED = "Created"
    QUEUED = "Queued"
    PROCESSING = "Processing"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"
    BLOCKED = "Blocked"



class AuditLevel(Enum):
    INFO = "Info"
    WARNING = "Warning"
    ERROR = "Error"
    SECURITY = "Security"


class RiskLevel(Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"