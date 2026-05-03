from __future__ import annotations

from datetime import datetime

from models.transaction import Transaction
from models.enums import TransactionStatus
from models.errors import (
    InvalidOperationError,
    TransactionNotFoundError,
)


class TransactionQueue:
    TERMINAL_STATUSES = {
        TransactionStatus.COMPLETED,
        TransactionStatus.FAILED,
        TransactionStatus.CANCELLED,
        TransactionStatus.BLOCKED,
    }

    def __init__(self):
        self._transactions: dict[str, Transaction] = {}

    def add(self, transaction: Transaction) -> Transaction:
        if transaction.transaction_id in self._transactions:
            raise InvalidOperationError(
                f"Transaction already exists: {transaction.transaction_id}"
            )

        if transaction.status in self.TERMINAL_STATUSES:
            raise InvalidOperationError(
                f"Cannot queue transaction with status: {transaction.status.value}"
            )

        transaction.mark_queued()
        self._transactions[transaction.transaction_id] = transaction

        return transaction

    def cancel(self, transaction_id: str) -> Transaction:
        transaction = self._get_transaction_or_raise(transaction_id)

        if transaction.status == TransactionStatus.PROCESSING:
            raise InvalidOperationError("Cannot cancel processing transaction")

        if transaction.status in self.TERMINAL_STATUSES:
            raise InvalidOperationError(
                f"Cannot cancel transaction with status: {transaction.status.value}"
            )

        transaction.mark_cancelled()
        return transaction

    def get_next(self, now: datetime | None = None) -> Transaction | None:
        ready_transactions = self.get_ready_transactions(now=now)

        if not ready_transactions:
            return None

        return ready_transactions[0]

    def get_ready_transactions(
        self,
        now: datetime | None = None,
    ) -> list[Transaction]:
        now = now or datetime.now()

        ready_transactions = [
            transaction
            for transaction in self._transactions.values()
            if transaction.is_ready(now)
        ]

        ready_transactions.sort(
            key=lambda transaction: (
                -transaction.priority,
                transaction.created_at,
            )
        )

        return ready_transactions

    def get_transaction(self, transaction_id: str) -> Transaction | None:
        return self._transactions.get(transaction_id)

    def get_all_transactions(self) -> list[Transaction]:
        return list(self._transactions.values())

    def get_active_transactions(self) -> list[Transaction]:
        return [
            transaction
            for transaction in self._transactions.values()
            if transaction.status == TransactionStatus.QUEUED
        ]

    def _get_transaction_or_raise(self, transaction_id: str) -> Transaction:
        transaction = self._transactions.get(transaction_id)

        if transaction is None:
            raise TransactionNotFoundError(
                f"Transaction not found: {transaction_id}"
            )

        return transaction

    def __len__(self) -> int:
        return len(self.get_active_transactions())