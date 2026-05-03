from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid4

from models.enums import Currency, TransactionStatus, TransactionType
from models.errors import InvalidOperationError


@dataclass
class Transaction:
    type: TransactionType
    amount: Decimal | int | float | str
    currency: Currency = Currency.RUB
    sender_account_id: str | None = None
    receiver_account_id: str | None = None
    fee: Decimal | int | float | str = Decimal("0")
    status: TransactionStatus = TransactionStatus.CREATED
    failure_reason: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    scheduled_at: datetime | None = None
    processed_at: datetime | None = None
    priority: int = 0
    transaction_id: str = field(default_factory=lambda: f"tx_{uuid4().hex[:10]}")
    retries: int = 0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.type = self._coerce_enum(
            value=self.type,
            enum_class=TransactionType,
            field_name="transaction type",
        )

        self.currency = self._coerce_enum(
            value=self.currency,
            enum_class=Currency,
            field_name="currency",
        )

        self.status = self._coerce_enum(
            value=self.status,
            enum_class=TransactionStatus,
            field_name="transaction status",
        )

        self.amount = self._to_decimal(self.amount)
        self.fee = self._to_decimal(self.fee)

        if self.amount <= 0:
            raise InvalidOperationError("Transaction amount must be positive")

        if self.fee < 0:
            raise InvalidOperationError("Transaction fee cannot be negative")

        if not isinstance(self.priority, int):
            raise InvalidOperationError("Transaction priority must be an integer")

    @staticmethod
    def _to_decimal(value: Decimal | int | float | str) -> Decimal:
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            raise InvalidOperationError(f"Invalid decimal value: {value}")

    @staticmethod
    def _coerce_enum(value, enum_class, field_name: str):
        if isinstance(value, enum_class):
            return value

        if isinstance(value, str):
            normalized = value.lower().strip()

            for item in enum_class:
                if item.value.lower() == normalized or item.name.lower() == normalized:
                    return item

        raise InvalidOperationError(f"Invalid {field_name}: {value}")

    def is_ready(self, now: datetime | None = None) -> bool:
        now = now or datetime.now()

        if self.status != TransactionStatus.QUEUED:
            return False

        if self.scheduled_at is None:
            return True

        return self.scheduled_at <= now

    def mark_queued(self) -> None:
        self.status = TransactionStatus.QUEUED
        self.failure_reason = None

    def mark_processing(self) -> None:
        self.status = TransactionStatus.PROCESSING

    def mark_completed(self, processed_at: datetime | None = None) -> None:
        self.status = TransactionStatus.COMPLETED
        self.failure_reason = None
        self.processed_at = processed_at or datetime.now()

    def mark_failed(
        self,
        reason: str,
        processed_at: datetime | None = None,
    ) -> None:
        self.status = TransactionStatus.FAILED
        self.failure_reason = reason
        self.processed_at = processed_at or datetime.now()

    def mark_blocked(
        self,
        reason: str,
        processed_at: datetime | None = None,
    ) -> None:
        self.status = TransactionStatus.BLOCKED
        self.failure_reason = reason
        self.processed_at = processed_at or datetime.now()

    def mark_cancelled(self) -> None:
        self.status = TransactionStatus.CANCELLED
        self.failure_reason = "Transaction was cancelled"

    def to_dict(self) -> dict:
        return {
            "transaction_id": self.transaction_id,
            "type": self.type.value,
            "amount": str(self.amount),
            "currency": self.currency.value,
            "fee": str(self.fee),
            "sender_account_id": self._stringify_id(self.sender_account_id),
            "receiver_account_id": self._stringify_id(self.receiver_account_id),
            "status": self.status.value,
            "failure_reason": self.failure_reason,
            "created_at": self.created_at.isoformat(),
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "priority": self.priority,
            "retries": self.retries,
            "metadata": self.metadata,
        }

    @staticmethod
    def _stringify_id(value):
        if isinstance(value, UUID):
            return str(value)

        return value

    def __str__(self) -> str:
        return (
            f"Transaction | "
            f"id={self.transaction_id} | "
            f"type={self.type.value} | "
            f"amount={self.amount} {self.currency.value} | "
            f"fee={self.fee} | "
            f"status={self.status.value} | "
            f"priority={self.priority}"
        )
