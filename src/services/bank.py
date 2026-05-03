from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Type

from models.client import Client
from models.enums import AccountStatus, ClientStatus, Currency

from models.accounts import BankAccount

from models.errors import (
    InvalidOperationError,
    AuthenticationError,
    ClientBlockedError,
    ClientNotFoundError,
    AccountNotFoundError,
)


class Bank:
    EXCHANGE_RATES_TO_RUB = {
        Currency.RUB: Decimal("1"),
        Currency.USD: Decimal("90"),
        Currency.EUR: Decimal("100"),
        Currency.KZT: Decimal("0.2"),
        Currency.CNY: Decimal("12.5"),
    }

    def __init__(
        self,
        name: str,
        audit_log: Any | None = None,
        risk_analyzer: Any | None = None,
        enforce_time_restrictions: bool = True,
    ):
        if not isinstance(name, str) or not name.strip():
            raise InvalidOperationError("Bank name cannot be empty")

        self.name = name.strip()

        self.clients: dict[str, Client] = {}
        self.accounts: dict[str, BankAccount] = {}

        self.audit_log = audit_log
        self.risk_analyzer = risk_analyzer

        self.enforce_time_restrictions = enforce_time_restrictions
        self.security_events: list[dict] = []

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

    @staticmethod
    def _is_night_time(now: datetime | None = None) -> bool:
        now = now or datetime.now()
        return 0 <= now.hour < 5

    def _check_operation_time(
        self,
        operation_name: str,
        now: datetime | None = None,
    ) -> None:
        if not self.enforce_time_restrictions:
            return

        if self._is_night_time(now):
            event_time = now or datetime.now()

            event = {
                "operation": operation_name,
                "reason": "Operations are forbidden from 00:00 to 05:00",
                "time": event_time.isoformat(),
            }

            self.security_events.append(event)

            self._write_audit(
                level="security",
                event_type="night_operation_blocked",
                message=f"Operation {operation_name} was blocked at night",
                data=event,
            )

            raise InvalidOperationError(
                "Operations are forbidden from 00:00 to 05:00"
            )

    def _get_client_or_raise(self, client_id: str) -> Client:
        client = self.clients.get(client_id)

        if client is None:
            raise ClientNotFoundError(f"Client not found: {client_id}")

        return client

    def _get_account_or_raise(self, account_id: str) -> BankAccount:
        account = self.accounts.get(account_id)

        if account is None:
            raise AccountNotFoundError(f"Account not found: {account_id}")

        return account

    def _validate_account_class(
        self,
        account_type: type[BankAccount],
    ) -> type[BankAccount]:
        if not isinstance(account_type, type):
            raise InvalidOperationError("Account type must be a class")

        if not issubclass(account_type, BankAccount):
            raise InvalidOperationError(
                "Account type must inherit from BankAccount"
            )

        return account_type

    def _convert_to_currency(
        self,
        amount: Decimal,
        from_currency: Currency,
        to_currency: Currency,
    ) -> Decimal:
        if from_currency == to_currency:
            return amount

        amount_in_rub = amount * self.EXCHANGE_RATES_TO_RUB[from_currency]
        converted = amount_in_rub / self.EXCHANGE_RATES_TO_RUB[to_currency]

        return converted.quantize(Decimal("0.01"))

    def add_client(
        self,
        full_name: str,
        age: int,
        contacts: dict | None = None,
        pin: str | None = None,
        client_id: str | None = None,
    ) -> Client:
        client = Client(
            client_id=client_id,
            full_name=full_name,
            age=age,
            contacts=contacts,
            pin=pin,
        )

        if client.client_id in self.clients:
            raise InvalidOperationError(
                f"Client with ID {client.client_id} already exists"
            )

        self.clients[client.client_id] = client

        self._write_audit(
            level="info",
            event_type="client_created",
            message=f"Client {client.full_name} was created",
            data=client.get_client_info(),
        )

        return client

    def open_account(
        self,
        client_id: str,
        account_type: type[BankAccount] = BankAccount,
        currency: Currency = Currency.RUB,
        initial_balance: Decimal | int | float | str = Decimal("0"),
        now: datetime | None = None,
        **account_kwargs,
    ) -> BankAccount:
        self._check_operation_time("open_account", now=now)

        client = self._get_client_or_raise(client_id)
        client.ensure_active()

        account_class = self._validate_account_class(account_type)

        account = account_class(
            owner_id=client.client_id,
            balance=initial_balance,
            currency=currency,
            **account_kwargs,
        )

        self.accounts[account.account_id] = account
        client.add_account(account.account_id)

        self._write_audit(
            level="info",
            event_type="account_opened",
            message=f"Account {account.account_id} was opened for client {client.client_id}",
            data=account.get_account_info(),
        )

        return account

    def close_account(
        self,
        account_id: str,
        now: datetime | None = None,
        require_zero_balance: bool = False,
    ) -> None:
        self._check_operation_time("close_account", now=now)

        account = self._get_account_or_raise(account_id)

        if require_zero_balance and account.balance != Decimal("0"):
            raise InvalidOperationError(
                "Cannot close account with non-zero balance"
            )

        account.close()

        self._write_audit(
            level="info",
            event_type="account_closed",
            message=f"Account {account_id} was closed",
            data=account.get_account_info(),
        )

    def freeze_account(
        self,
        account_id: str,
        reason: str | None = None,
    ) -> None:
        account = self._get_account_or_raise(account_id)
        account.freeze()

        self._write_audit(
            level="warning",
            event_type="account_frozen",
            message=f"Account {account_id} was frozen",
            data={
                "account_id": account_id,
                "reason": reason,
            },
        )

    def unfreeze_account(
        self,
        account_id: str,
        reason: str | None = None,
    ) -> None:
        account = self._get_account_or_raise(account_id)
        account.unfreeze()

        self._write_audit(
            level="info",
            event_type="account_unfrozen",
            message=f"Account {account_id} was unfrozen",
            data={
                "account_id": account_id,
                "reason": reason,
            },
        )

    def authenticate_client(
        self,
        client_id: str,
        pin: str,
    ) -> bool:
        client = self._get_client_or_raise(client_id)

        if client.status == ClientStatus.BLOCKED:
            raise ClientBlockedError("Client is blocked")

        try:
            is_valid = client.check_pin(pin)
        except AuthenticationError:
            raise

        if is_valid:
            client.register_successful_login()

            self._write_audit(
                level="info",
                event_type="client_authenticated",
                message=f"Client {client_id} was authenticated",
                data={"client_id": client_id},
            )

            return True

        client.register_failed_login()

        self._write_audit(
            level="warning",
            event_type="authentication_failed",
            message=f"Authentication failed for client {client_id}",
            data={
                "client_id": client_id,
                "failed_login_attempts": client.failed_login_attempts,
            },
        )

        if client.status == ClientStatus.BLOCKED:
            self._write_audit(
                level="security",
                event_type="client_blocked",
                message=f"Client {client_id} was blocked after 3 failed login attempts",
                data={"client_id": client_id},
            )

        return False

    def search_accounts(
        self,
        client_id: str | None = None,
        status: AccountStatus | None = None,
        currency: Currency | None = None,
        account_type: type[BankAccount] | None = None,
        min_balance: Decimal | int | float | str | None = None,
        max_balance: Decimal | int | float | str | None = None,
        include_closed: bool = True,
    ) -> list[BankAccount]:
        result = list(self.accounts.values())

        if client_id is not None:
            result = [
                account
                for account in result
                if account.owner_id == client_id
            ]

        if status is not None:
            result = [
                account
                for account in result
                if account.status == status
            ]

        if currency is not None:
            result = [
                account
                for account in result
                if account.currency == currency
            ]

        if account_type is not None:
            account_class = self._validate_account_class(account_type)

            result = [
                account
                for account in result
                if isinstance(account, account_class)
            ]

        if min_balance is not None:
            min_balance = Decimal(str(min_balance))

            result = [
                account
                for account in result
                if account.balance >= min_balance
            ]

        if max_balance is not None:
            max_balance = Decimal(str(max_balance))

            result = [
                account
                for account in result
                if account.balance <= max_balance
            ]

        if not include_closed:
            result = [
                account
                for account in result
                if account.status != AccountStatus.CLOSED
            ]

        return result

    def get_client_accounts(
        self,
        client_id: str,
        include_closed: bool = True,
    ) -> list[BankAccount]:
        client = self._get_client_or_raise(client_id)

        accounts = [
            self.accounts[account_id]
            for account_id in client.account_ids
            if account_id in self.accounts
        ]

        if not include_closed:
            accounts = [
                account
                for account in accounts
                if account.status != AccountStatus.CLOSED
            ]

        return accounts

    def get_total_balance(
        self,
        base_currency: Currency = Currency.RUB,
        convert: bool = True,
        include_closed: bool = False,
    ) -> Decimal | dict[str, str]:
        accounts = self.search_accounts(include_closed=include_closed)

        if not convert:
            totals: dict[Currency, Decimal] = {
                currency: Decimal("0")
                for currency in Currency
            }

            for account in accounts:
                totals[account.currency] += account.balance

            return {
                currency.value: str(amount)
                for currency, amount in totals.items()
            }

        total = Decimal("0")

        for account in accounts:
            total += self._convert_to_currency(
                amount=account.balance,
                from_currency=account.currency,
                to_currency=base_currency,
            )

        return total.quantize(Decimal("0.01"))

    def get_clients_ranking(
        self,
        top: int | None = None,
        base_currency: Currency = Currency.RUB,
        include_blocked: bool = True,
    ) -> list[dict]:
        ranking = []

        for client in self.clients.values():
            if not include_blocked and client.status == ClientStatus.BLOCKED:
                continue

            accounts = self.get_client_accounts(
                client.client_id,
                include_closed=False,
            )

            total_balance = Decimal("0")

            for account in accounts:
                total_balance += self._convert_to_currency(
                    amount=account.balance,
                    from_currency=account.currency,
                    to_currency=base_currency,
                )

            ranking.append(
                {
                    "client_id": str(client.client_id),
                    "full_name": client.full_name,
                    "status": client.status.value,
                    "accounts_count": len(accounts),
                    "total_balance": total_balance.quantize(Decimal("0.01")),
                    "currency": base_currency.value,
                }
            )

        ranking.sort(
            key=lambda item: item["total_balance"],
            reverse=True,
        )

        if top is not None:
            ranking = ranking[:top]

        for item in ranking:
            item["total_balance"] = str(item["total_balance"])

        return ranking

    def mark_suspicious_action(
        self,
        client_id: str,
        reason: str,
        data: dict | None = None,
    ) -> None:
        client = self._get_client_or_raise(client_id)

        event = {
            "client_id": client_id,
            "reason": reason,
            "data": data or {},
            "created_at": datetime.now().isoformat(),
        }

        client.mark_suspicious_action(reason=reason, data=data)
        self.security_events.append(event)

        self._write_audit(
            level="security",
            event_type="suspicious_action",
            message=f"Suspicious action for client {client_id}: {reason}",
            data=event,
        )

    def get_bank_info(self) -> dict:
        return {
            "name": self.name,
            "clients_count": len(self.clients),
            "accounts_count": len(self.accounts),
            "total_balance_rub": str(
                self.get_total_balance(base_currency=Currency.RUB)
            ),
            "security_events_count": len(self.security_events),
        }

    def __str__(self) -> str:
        return (
            f"Bank | "
            f"name={self.name} | "
            f"clients={len(self.clients)} | "
            f"accounts={len(self.accounts)}"
        )
