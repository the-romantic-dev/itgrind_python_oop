from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from models.enums import (
    AccountStatus,
    Currency,
    TransactionStatus,
    TransactionType,
)
from models.transaction import Transaction
from models.accounts import BankAccount, PremiumAccount
from services.transaction_queue import TransactionQueue

from models.errors import (
    AccountClosedError,
    AccountFrozenError,
    AccountNotFoundError,
    ClientBlockedError,
    ClientNotFoundError,
    InsufficientFundsError,
    InvalidOperationError,
    RiskBlockedError,
    TransactionCancelledError,
    TransactionValidationError,
)


class TransactionProcessor:
    BUSINESS_ERRORS = (
        AccountClosedError,
        AccountFrozenError,
        AccountNotFoundError,
        ClientBlockedError,
        ClientNotFoundError,
        InsufficientFundsError,
        InvalidOperationError,
        RiskBlockedError,
        TransactionCancelledError,
        TransactionValidationError,
    )

    EXCHANGE_RATES_TO_RUB = {
        Currency.RUB: Decimal("1"),
        Currency.USD: Decimal("90"),
        Currency.EUR: Decimal("100"),
        Currency.KZT: Decimal("0.2"),
        Currency.CNY: Decimal("12.5"),
    }

    def __init__(
        self,
        bank,
        audit_log: Any | None = None,
        risk_analyzer: Any | None = None,
        max_retries: int = 3,
        external_transfer_fee_rate: Decimal | int | float | str = Decimal("0.01"),
        external_transfer_min_fee: Decimal | int | float | str = Decimal("50"),
    ):
        self.bank = bank
        self.audit_log = audit_log if audit_log is not None else getattr(bank, "audit_log", None)
        self.risk_analyzer = risk_analyzer if risk_analyzer is not None else getattr(bank, "risk_analyzer", None)

        self.max_retries = max_retries
        self.external_transfer_fee_rate = Decimal(str(external_transfer_fee_rate))
        self.external_transfer_min_fee = Decimal(str(external_transfer_min_fee))

        if self.max_retries < 0:
            raise InvalidOperationError("Max retries cannot be negative")

        if self.external_transfer_fee_rate < 0:
            raise InvalidOperationError("External transfer fee rate cannot be negative")

        if self.external_transfer_min_fee < 0:
            raise InvalidOperationError("External transfer minimum fee cannot be negative")

    def process_queue(
        self,
        queue: TransactionQueue,
        now: datetime | None = None,
    ) -> list[Transaction]:
        processed_transactions = []

        while True:
            transaction = queue.get_next(now=now)

            if transaction is None:
                break

            processed_transaction = self.process(transaction, now=now)
            processed_transactions.append(processed_transaction)

        return processed_transactions

    def process(
        self,
        transaction: Transaction,
        now: datetime | None = None,
    ) -> Transaction:
        now = now or datetime.now()

        if transaction.status == TransactionStatus.CANCELLED:
            return transaction

        if transaction.status in {
            TransactionStatus.COMPLETED,
            TransactionStatus.FAILED,
            TransactionStatus.BLOCKED,
        }:
            raise InvalidOperationError(
                f"Cannot process transaction with status: {transaction.status.value}"
            )

        try:
            transaction.mark_processing()

            self._validate_transaction(transaction)
            self._check_night_restriction(transaction, now=now)
            self._analyze_risk(transaction, now=now)

            if transaction.type == TransactionType.DEPOSIT:
                self._process_deposit(transaction)

            elif transaction.type == TransactionType.WITHDRAW:
                self._process_withdraw(transaction)

            elif transaction.type == TransactionType.TRANSFER:
                self._process_transfer(transaction)

            elif transaction.type == TransactionType.EXTERNAL_TRANSFER:
                self._process_external_transfer(transaction)

            else:
                raise TransactionValidationError(
                    f"Unsupported transaction type: {transaction.type.value}"
                )

            transaction.mark_completed(processed_at=now)

            self._write_audit(
                level="info",
                event_type="transaction_completed",
                message=f"Transaction {transaction.transaction_id} was completed",
                data=transaction.to_dict(),
            )

        except RiskBlockedError as error:
            transaction.mark_blocked(str(error), processed_at=now)

            self._write_audit(
                level="security",
                event_type="transaction_blocked",
                message=f"Transaction {transaction.transaction_id} was blocked",
                data=transaction.to_dict(),
            )

        except self.BUSINESS_ERRORS as error:
            transaction.mark_failed(str(error), processed_at=now)

            self._write_audit(
                level="error",
                event_type="transaction_failed",
                message=f"Transaction {transaction.transaction_id} failed",
                data=transaction.to_dict(),
            )

        except Exception as error:
            transaction.retries += 1
            transaction.failure_reason = str(error)

            if transaction.retries <= self.max_retries:
                transaction.status = TransactionStatus.QUEUED

                self._write_audit(
                    level="warning",
                    event_type="transaction_retry",
                    message=f"Transaction {transaction.transaction_id} was returned to queue",
                    data=transaction.to_dict(),
                )
            else:
                transaction.mark_failed(str(error), processed_at=now)

                self._write_audit(
                    level="error",
                    event_type="transaction_failed_after_retries",
                    message=f"Transaction {transaction.transaction_id} failed after retries",
                    data=transaction.to_dict(),
                )

        return transaction

    def _validate_transaction(self, transaction: Transaction) -> None:
        if transaction.amount <= 0:
            raise TransactionValidationError("Transaction amount must be positive")

        if transaction.fee < 0:
            raise TransactionValidationError("Transaction fee cannot be negative")

        if transaction.type == TransactionType.DEPOSIT:
            if transaction.receiver_account_id is None:
                raise TransactionValidationError(
                    "Deposit requires receiver account ID"
                )

        elif transaction.type == TransactionType.WITHDRAW:
            if transaction.sender_account_id is None:
                raise TransactionValidationError(
                    "Withdraw requires sender account ID"
                )

        elif transaction.type == TransactionType.TRANSFER:
            if transaction.sender_account_id is None:
                raise TransactionValidationError(
                    "Transfer requires sender account ID"
                )

            if transaction.receiver_account_id is None:
                raise TransactionValidationError(
                    "Transfer requires receiver account ID"
                )

            if transaction.sender_account_id == transaction.receiver_account_id:
                raise TransactionValidationError(
                    "Sender and receiver accounts must be different"
                )

        elif transaction.type == TransactionType.EXTERNAL_TRANSFER:
            if transaction.sender_account_id is None:
                raise TransactionValidationError(
                    "External transfer requires sender account ID"
                )

            if transaction.receiver_account_id is None:
                raise TransactionValidationError(
                    "External transfer requires external receiver ID"
                )

        else:
            raise TransactionValidationError(
                f"Unsupported transaction type: {transaction.type.value}"
            )

    def _check_night_restriction(
        self,
        transaction: Transaction,
        now: datetime,
    ) -> None:
        enforce_time_restrictions = getattr(
            self.bank,
            "enforce_time_restrictions",
            True,
        )

        if not enforce_time_restrictions:
            return

        if 0 <= now.hour < 5:
            raise RiskBlockedError(
                "Transactions are forbidden from 00:00 to 05:00"
            )

    def _analyze_risk(
        self,
        transaction: Transaction,
        now: datetime,
    ) -> None:
        if self.risk_analyzer is None:
            return

        try:
            assessment = self.risk_analyzer.analyze(
                transaction=transaction,
                bank=self.bank,
                now=now,
            )
        except TypeError:
            assessment = self.risk_analyzer.analyze(transaction, self.bank, now)

        level = self._extract_risk_level(assessment)

        if level == "high":
            raise RiskBlockedError(
                "Transaction was blocked by risk analyzer"
            )

        if level == "medium":
            self._write_audit(
                level="warning",
                event_type="suspicious_transaction",
                message=f"Transaction {transaction.transaction_id} was marked as suspicious",
                data={
                    "transaction": transaction.to_dict(),
                    "risk_assessment": self._assessment_to_dict(assessment),
                },
            )

    def _extract_risk_level(self, assessment) -> str | None:
        if assessment is None:
            return None

        if isinstance(assessment, dict):
            level = assessment.get("level")
        else:
            level = getattr(assessment, "level", None)

        if level is None:
            return None

        if hasattr(level, "value"):
            return str(level.value).lower()

        return str(level).lower()

    def _assessment_to_dict(self, assessment) -> dict:
        if assessment is None:
            return {}

        if isinstance(assessment, dict):
            return assessment

        if hasattr(assessment, "to_dict"):
            return assessment.to_dict()

        return {
            "level": str(getattr(assessment, "level", None)),
            "score": getattr(assessment, "score", None),
            "reasons": getattr(assessment, "reasons", None),
        }

    def _process_deposit(self, transaction: Transaction) -> None:
        receiver_account = self._get_account(transaction.receiver_account_id)

        amount_to_credit = self._convert_amount(
            amount=transaction.amount,
            from_currency=transaction.currency,
            to_currency=receiver_account.currency,
        )

        transaction.fee = Decimal("0")
        receiver_account.deposit(amount_to_credit)

    def _process_withdraw(self, transaction: Transaction) -> None:
        sender_account = self._get_account(transaction.sender_account_id)

        self._validate_sender_account_for_debit(
            account=sender_account,
            transaction=transaction,
        )

        transaction.fee = self._calculate_fee(
            transaction=transaction,
            sender_account=sender_account,
        )

        amount_to_debit = self._convert_amount(
            amount=transaction.amount + transaction.fee,
            from_currency=transaction.currency,
            to_currency=sender_account.currency,
        )

        self._debit(account=sender_account, amount=amount_to_debit)

    def _process_transfer(self, transaction: Transaction) -> None:
        sender_account = self._get_account(transaction.sender_account_id)
        receiver_account = self._get_account(transaction.receiver_account_id)

        self._validate_sender_account_for_debit(
            account=sender_account,
            transaction=transaction,
        )

        transaction.fee = self._calculate_fee(
            transaction=transaction,
            sender_account=sender_account,
        )

        amount_to_debit = self._convert_amount(
            amount=transaction.amount + transaction.fee,
            from_currency=transaction.currency,
            to_currency=sender_account.currency,
        )

        amount_to_credit = self._convert_amount(
            amount=transaction.amount,
            from_currency=transaction.currency,
            to_currency=receiver_account.currency,
        )

        self._debit(account=sender_account, amount=amount_to_debit)
        receiver_account.deposit(amount_to_credit)

    def _process_external_transfer(self, transaction: Transaction) -> None:
        sender_account = self._get_account(transaction.sender_account_id)

        self._validate_sender_account_for_debit(
            account=sender_account,
            transaction=transaction,
        )

        transaction.fee = self._calculate_fee(
            transaction=transaction,
            sender_account=sender_account,
        )

        amount_to_debit = self._convert_amount(
            amount=transaction.amount + transaction.fee,
            from_currency=transaction.currency,
            to_currency=sender_account.currency,
        )

        self._debit(account=sender_account, amount=amount_to_debit)

    def _validate_sender_account_for_debit(
        self,
        account: BankAccount,
        transaction: Transaction,
    ) -> None:
        if account.status == AccountStatus.FROZEN:
            raise AccountFrozenError("Sender account is frozen")

        if account.status == AccountStatus.CLOSED:
            raise AccountClosedError("Sender account is closed")

        if transaction.type in {
            TransactionType.TRANSFER,
            TransactionType.EXTERNAL_TRANSFER,
        }:
            if account.balance < 0 and not isinstance(account, PremiumAccount):
                raise InsufficientFundsError(
                    "Transfers from negative balance are forbidden"
                )

    def _calculate_fee(
        self,
        transaction: Transaction,
        sender_account: BankAccount | None = None,
    ) -> Decimal:
        fee = Decimal("0")

        if transaction.type == TransactionType.EXTERNAL_TRANSFER:
            external_fee = transaction.amount * self.external_transfer_fee_rate

            if external_fee < self.external_transfer_min_fee:
                external_fee = self.external_transfer_min_fee

            fee += external_fee

        if sender_account is not None and isinstance(sender_account, PremiumAccount):
            if transaction.type in {
                TransactionType.WITHDRAW,
                TransactionType.TRANSFER,
                TransactionType.EXTERNAL_TRANSFER,
            }:
                premium_fee = self._convert_amount(
                    amount=sender_account.fixed_fee,
                    from_currency=sender_account.currency,
                    to_currency=transaction.currency,
                )

                fee += premium_fee

        return fee.quantize(Decimal("0.01"))

    def _debit(
        self,
        account: BankAccount,
        amount: Decimal,
    ) -> Decimal:
        if isinstance(account, PremiumAccount):
            try:
                return account.withdraw(amount, apply_fee=False)
            except TypeError:
                return account.withdraw(amount)

        return account.withdraw(amount)

    def _get_account(self, account_id: str | None) -> BankAccount:
        if account_id is None:
            raise AccountNotFoundError("Account ID is required")

        if hasattr(self.bank, "_get_account_or_raise"):
            return self.bank._get_account_or_raise(account_id)

        account = self.bank.accounts.get(account_id)

        if account is None:
            raise AccountNotFoundError(f"Account not found: {account_id}")

        return account

    def _convert_amount(
        self,
        amount: Decimal,
        from_currency: Currency,
        to_currency: Currency,
    ) -> Decimal:
        if from_currency == to_currency:
            return amount

        if hasattr(self.bank, "_convert_to_currency"):
            return self.bank._convert_to_currency(
                amount=amount,
                from_currency=from_currency,
                to_currency=to_currency,
            )

        amount_in_rub = amount * self.EXCHANGE_RATES_TO_RUB[from_currency]
        converted = amount_in_rub / self.EXCHANGE_RATES_TO_RUB[to_currency]

        return converted.quantize(Decimal("0.01"))

    def _write_audit(
        self,
        level: str,
        event_type: str,
        message: str,
        data: dict | None = None,
    ) -> None:
        if self.audit_log is not None and hasattr(self.audit_log, "log"):
            self.audit_log.log(
                level=level,
                event_type=event_type,
                message=message,
                data=data or {},
            )