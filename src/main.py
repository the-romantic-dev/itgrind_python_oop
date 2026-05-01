from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from enum import Enum
import uuid


@dataclass
class PersonalData:
    first_name: str
    last_name: str
    middle_name: str | None
    brith_date: date


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


class AccountFrozenError(Exception):
    pass


class AccountClosedError(Exception):
    pass


class InvalidOperationError(Exception):
    pass


class InsufficientFundsError(Exception):
    pass


class AbstractAccount(ABC):
    def __init__(
        self,
        id: uuid.UUID,
        personal_data: PersonalData,
        status: AccountStatus,
        init_balance: float = 0.0,
    ):
        self.id = id
        self.personal_data = personal_data
        self.status = status
        self._balance = init_balance

    @abstractmethod
    def deposit(self, amount: float):
        pass

    @abstractmethod
    def withdraw(self, amount: float):
        pass

    @abstractmethod
    def get_account_info(self):
        pass


class BankAccount(AbstractAccount):
    def __init__(
        self,
        personal_data: PersonalData,
        currency: Currency,
        status: AccountStatus,
        init_balance: float = 0.0,
        id: uuid.UUID | None = None,
    ):
        self._validate_personal_data(personal_data)
        self._validate_currency(currency)
        self._validate_status(status)
        self._validate_amount(init_balance, allow_zero=True, name="Initial balance")

        super().__init__(id or uuid.uuid4(), personal_data, status, init_balance)
        self.currency = currency
        self.withdrawal_limit = 10_000.0

    @staticmethod
    def _validate_personal_data(personal_data: PersonalData):
        if not isinstance(personal_data, PersonalData):
            raise InvalidOperationError("Personal data must be a PersonalData instance")
        if not personal_data.first_name or not personal_data.last_name:
            raise InvalidOperationError("First name and last name are required")

    @staticmethod
    def _validate_currency(currency: Currency):
        if not isinstance(currency, Currency):
            raise InvalidOperationError("Currency must be a Currency enum value")

    @staticmethod
    def _validate_status(status: AccountStatus):
        if not isinstance(status, AccountStatus):
            raise InvalidOperationError("Status must be an AccountStatus enum value")

    @staticmethod
    def _validate_amount(amount: float, allow_zero: bool = False, name: str = "Amount"):
        if not isinstance(amount, (int, float)):
            raise InvalidOperationError(f"{name} must be a number")
        if allow_zero:
            if amount < 0:
                raise InvalidOperationError(f"{name} cannot be negative")
        elif amount <= 0:
            raise InvalidOperationError(f"{name} must be greater than 0")

    def _check_status(self):
        if self.status == AccountStatus.FROZEN:
            raise AccountFrozenError("Account is frozen")
        if self.status == AccountStatus.CLOSED:
            raise AccountClosedError("Account is closed")

    def withdraw(self, amount: float):
        self._check_status()
        self._validate_amount(amount)
        if amount > self.withdrawal_limit:
            raise InvalidOperationError(
                f"Withdrawal cannot exceed limit {self.withdrawal_limit}"
            )
        if amount > self._balance:
            raise InsufficientFundsError("Insufficient funds")
        self._balance -= amount

    def deposit(self, amount: float):
        self._check_status()
        self._validate_amount(amount)
        self._balance += amount

    def get_account_info(self):
        return {
            "account_type": self.__class__.__name__,
            "id": self.id,
            "personal_data": self.personal_data,
            "balance": self._balance,
            "currency": self.currency,
            "account_status": self.status,
            "withdrawal_limit": self.withdrawal_limit,
        }

    def __str__(self):
        fio = self._format_owner()
        return (
            f"Account type: {self.__class__.__name__}\n"
            f"Client: {fio}\n"
            f"Birth date: {self.personal_data.brith_date.isoformat()}\n"
            f"Account ID: ****{str(self.id)[-4:]}\n"
            f"Status: {self.status.value}\n"
            f"Balance: {self._balance:.2f} {self.currency.value}\n"
            f"Withdrawal limit: {self.withdrawal_limit:.2f} {self.currency.value}"
        )

    def _format_owner(self):
        parts = [
            self.personal_data.last_name,
            self.personal_data.first_name,
            self.personal_data.middle_name or "",
        ]
        return " ".join(part for part in parts if part)


class SavingsAccount(BankAccount):
    def __init__(
        self,
        personal_data: PersonalData,
        currency: Currency,
        status: AccountStatus,
        min_balance: float,
        monthly_interest: float,
        init_balance: float = 0.0,
        id: uuid.UUID | None = None,
    ):
        self._validate_amount(min_balance, allow_zero=True, name="Minimum balance")
        self._validate_amount(
            monthly_interest, allow_zero=True, name="Monthly interest"
        )
        if init_balance < min_balance:
            raise InvalidOperationError("Initial balance cannot be below minimum balance")

        self.min_balance = min_balance
        self.monthly_interest = monthly_interest
        super().__init__(personal_data, currency, status, init_balance, id)

    def withdraw(self, amount: float):
        self._check_status()
        self._validate_amount(amount)
        if amount > self.withdrawal_limit:
            raise InvalidOperationError(
                f"Withdrawal cannot exceed limit {self.withdrawal_limit}"
            )
        if self._balance - amount < self.min_balance:
            raise InsufficientFundsError("Withdrawal would break minimum balance")
        self._balance -= amount

    def apply_monthly_interest(self):
        self._check_status()
        self._balance *= 1 + self.monthly_interest

    def get_account_info(self):
        info = super().get_account_info()
        info.update(
            {
                "min_balance": self.min_balance,
                "monthly_interest": self.monthly_interest,
            }
        )
        return info

    def __str__(self):
        return (
            f"{super().__str__()}\n"
            f"Minimum balance: {self.min_balance:.2f} {self.currency.value}\n"
            f"Monthly interest: {self.monthly_interest * 100:.2f}%"
        )


class PremiumAccount(BankAccount):
    def __init__(
        self,
        personal_data: PersonalData,
        currency: Currency,
        status: AccountStatus,
        withdrawal_fee: float,
        init_balance: float = 0.0,
        overdraft_limit: float = 100_000.0,
        id: uuid.UUID | None = None,
    ):
        self._validate_amount(withdrawal_fee, allow_zero=True, name="Withdrawal fee")
        self._validate_amount(overdraft_limit, allow_zero=True, name="Overdraft limit")

        self.withdrawal_fee = withdrawal_fee
        self.overdraft_limit = overdraft_limit
        super().__init__(personal_data, currency, status, init_balance, id)
        self.withdrawal_limit = 100_000.0

    def withdraw(self, amount: float):
        self._check_status()
        self._validate_amount(amount)
        if amount > self.withdrawal_limit:
            raise InvalidOperationError(
                f"Withdrawal cannot exceed limit {self.withdrawal_limit}"
            )

        total_amount = amount + self.withdrawal_fee
        if self._balance - total_amount < -self.overdraft_limit:
            raise InsufficientFundsError("Overdraft limit exceeded")
        self._balance -= total_amount

    def get_account_info(self):
        info = super().get_account_info()
        info.update(
            {
                "withdrawal_fee": self.withdrawal_fee,
                "overdraft_limit": self.overdraft_limit,
            }
        )
        return info

    def __str__(self):
        return (
            f"{super().__str__()}\n"
            f"Withdrawal fee: {self.withdrawal_fee:.2f} {self.currency.value}\n"
            f"Overdraft limit: {self.overdraft_limit:.2f} {self.currency.value}"
        )


class InvestmentAccount(BankAccount):
    ALLOWED_ASSETS = {"stocks", "bonds", "etf"}
    DEFAULT_YEARLY_GROWTH_RATES = {
        "stocks": 0.12,
        "bonds": 0.05,
        "etf": 0.08,
    }

    def __init__(
        self,
        personal_data: PersonalData,
        currency: Currency,
        status: AccountStatus,
        portfolio: dict[str, float] | None = None,
        yearly_growth_rates: dict[str, float] | None = None,
        init_balance: float = 0.0,
        id: uuid.UUID | None = None,
    ):
        super().__init__(personal_data, currency, status, init_balance, id)
        self.portfolio = self._validate_portfolio(portfolio or {})
        self.yearly_growth_rates = self._validate_growth_rates(
            yearly_growth_rates or self.DEFAULT_YEARLY_GROWTH_RATES
        )
        self.withdrawal_limit = 50_000.0

    def _validate_portfolio(self, portfolio: dict[str, float]):
        if not isinstance(portfolio, dict):
            raise InvalidOperationError("Portfolio must be a dictionary")

        result = {asset: 0.0 for asset in self.ALLOWED_ASSETS}
        for asset, amount in portfolio.items():
            if asset not in self.ALLOWED_ASSETS:
                raise InvalidOperationError(f"Unsupported asset: {asset}")
            self._validate_amount(amount, allow_zero=True, name=f"{asset} amount")
            result[asset] = float(amount)
        return result

    def _validate_growth_rates(self, growth_rates: dict[str, float]):
        if not isinstance(growth_rates, dict):
            raise InvalidOperationError("Growth rates must be a dictionary")

        result = self.DEFAULT_YEARLY_GROWTH_RATES.copy()
        for asset, rate in growth_rates.items():
            if asset not in self.ALLOWED_ASSETS:
                raise InvalidOperationError(f"Unsupported asset: {asset}")
            if not isinstance(rate, (int, float)):
                raise InvalidOperationError(f"{asset} growth rate must be a number")
            result[asset] = float(rate)
        return result

    def withdraw(self, amount: float):
        self._check_status()
        self._validate_amount(amount)
        if amount > self.withdrawal_limit:
            raise InvalidOperationError(
                f"Withdrawal cannot exceed limit {self.withdrawal_limit}"
            )
        if amount > self._balance:
            raise InsufficientFundsError("Insufficient cash balance")
        self._balance -= amount

    def project_yearly_growth(self):
        return sum(
            self.portfolio[asset] * self.yearly_growth_rates[asset]
            for asset in self.ALLOWED_ASSETS
        )

    def get_account_info(self):
        info = super().get_account_info()
        info.update(
            {
                "portfolio": self.portfolio.copy(),
                "yearly_growth_rates": self.yearly_growth_rates.copy(),
                "projected_yearly_growth": self.project_yearly_growth(),
            }
        )
        return info

    def __str__(self):
        portfolio = ", ".join(
            f"{asset}: {amount:.2f} {self.currency.value}"
            for asset, amount in sorted(self.portfolio.items())
        )
        return (
            f"{super().__str__()}\n"
            f"Portfolio: {portfolio}\n"
            f"Projected yearly growth: "
            f"{self.project_yearly_growth():.2f} {self.currency.value}"
        )
