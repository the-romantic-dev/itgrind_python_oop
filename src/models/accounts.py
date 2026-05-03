from abc import ABC, abstractmethod
from decimal import Decimal
import uuid

from models.enums import AccountStatus, Currency
from models.errors import AccountClosedError, AccountFrozenError, InsufficientFundsError, InvalidOperationError

class AbstractAccount(ABC):
    account_id: uuid.UUID
    owner_id: uuid.UUID
    _balance: Decimal
    status: AccountStatus

    @abstractmethod
    def deposit(self, amount: float):...

    @abstractmethod
    def withdraw(self, amount: float):...

    @abstractmethod
    def get_account_info(self):...


class BankAccount(AbstractAccount):

    def __init__(
        self,
        owner_id: uuid.UUID,
        account_id: uuid.UUID | None = None,
        balance: Decimal | int | float | str = Decimal("0"),
        currency: Currency = Currency.RUB,
        status: AccountStatus = AccountStatus.ACTIVE
    ):
        self._balance = self._to_decimal(balance)
        
        if self._balance < 0:
            raise InvalidOperationError('Balance can\'t be negative')

        self.owner_id = owner_id
        self.account_id = uuid.uuid4() if account_id is None else account_id
        self.currency = currency
        self.status = status

    @property
    def id(self) -> uuid.UUID:
        return self.account_id

    @property
    def balance(self) -> Decimal:
        return self._balance

    @staticmethod
    def _to_decimal(value: Decimal | int | float | str) -> Decimal:
        try:
            return Decimal(str(value))
        except Exception:
            raise InvalidOperationError(f"Некорректная сумма: {value}")

    def _check_status(self):
        if self.status == AccountStatus.FROZEN:
            raise AccountFrozenError("Account is frozen")
        if self.status == AccountStatus.CLOSED:
            raise AccountClosedError("Account is closed")

    def _validate_amount(self, amount: Decimal):
        amount = self._to_decimal(amount)
        if amount <= 0:
            raise InvalidOperationError('Amount can\'t be non positive') 
        return amount

    def withdraw(self, amount: Decimal | int | float | str) -> Decimal:
        self._check_status()
        amount = self._validate_amount(amount)
        if amount > self._balance:
            raise InsufficientFundsError("Insufficient funds")
        self._balance -= amount
        return self._balance

    def deposit(self, amount: Decimal | int | float | str):
        self._check_status()
        amount = self._validate_amount(amount)
        self._balance += amount

    def get_account_info(self):
        return {
            "account_type": self.__class__.__name__,
            "account_id": str(self.account_id),
            "owner_id": str(self.owner_id),
            "balance": str(self._balance),
            "currency": self.currency.value,
            "status": self.status.value,
        }
    
    def freeze(self) -> None:
        if self.status == AccountStatus.CLOSED:
            raise AccountClosedError("Not allowed to freeze closed account")

        self.status = AccountStatus.FROZEN

    def unfreeze(self) -> None:
        if self.status == AccountStatus.CLOSED:
            raise AccountClosedError("Not allowed to unfreeze closed account")

        self.status = AccountStatus.ACTIVE

    def close(self) -> None:
        self.status = AccountStatus.CLOSED

    def __str__(self):
        return (
            f"Account type: {self.__class__.__name__}\n"
            f"Client: {self.owner_id}\n"
            f"Account ID: ****{str(self.id)[-4:]}\n"
            f"Status: {self.status.value}\n"
            f"Balance: {self._balance} {self.currency.value}\n"
        )

class SavingsAccount(BankAccount):
    def __init__(
        self,
        owner_id: uuid.UUID,
        account_id: uuid.UUID | None = None,
        balance: Decimal | int | float | str = Decimal("0"),
        currency: Currency = Currency.RUB,
        status: AccountStatus = AccountStatus.ACTIVE,
        min_balance: Decimal | int | float | str = Decimal("0"),
        monthly_interest_rate: Decimal | int | float | str = Decimal("0")
    ):
        super().__init__(
            owner_id=owner_id,
            balance=balance,
            currency=currency,
            account_id=account_id,
            status=status,
        )
        self.min_balance = self._to_decimal(min_balance)
        self.monthly_interest_rate = self._to_decimal(monthly_interest_rate)

        if self.min_balance < 0:
            raise InvalidOperationError("Min balance can\'t be negative")

        if self.monthly_interest_rate < 0:
            raise InvalidOperationError("Monthly interest rate can\'t be negative")

        if self.balance < self.min_balance:
            raise InvalidOperationError(
                "Initial balance can\'t be less than minimal balance"
            )
        

    def withdraw(self, amount: Decimal | int | float | str) -> Decimal:
        self._check_status()
        amount = self._validate_amount(amount)

        balance_after = self.balance - amount

        if balance_after < self.min_balance:
            raise InsufficientFundsError(
                f"You can't withdraw {amount} {self.currency.value}"
                f"Min balance: {self.min_balance} {self.currency.value}"
            )

        self._balance = balance_after
        return self._balance

    def apply_monthly_interest(self) -> Decimal:
        self._check_status()

        interest = self.balance * self.monthly_interest_rate
        self._balance += interest

        return interest

    def get_account_info(self) -> dict:
        base_info = super().get_account_info()

        base_info.update(
            {
                "account_type": "SavingsAccount",
                "min_balance": str(self.min_balance),
                "monthly_interest_rate": str(self.monthly_interest_rate),
            }
        )
        return base_info

    def __str__(self):
        return (
            f"Account type: {self.__class__.__name__}\n"
            f"Client: {self.owner_id}\n"
            f"Account ID: ****{str(self.id)[-4:]}\n"
            f"Status: {self.status.value}\n"
            f"Balance: {self._balance} {self.currency.value}\n"
            f"Min balance: {self.min_balance} {self.currency.value}\n"
            f"Monthly rate: {self.monthly_interest_rate}\n"
        )

class PremiumAccount(BankAccount):
    def __init__(
        self,
        owner_id: uuid.UUID,
        account_id: uuid.UUID | None = None,
        balance: Decimal | int | float | str = Decimal("0"),
        currency: Currency = Currency.RUB,
        status: AccountStatus = AccountStatus.ACTIVE,
        overdraft_limit: Decimal | int | float | str = Decimal("50000"),
        fixed_fee: Decimal | int | float | str = Decimal("100")
        ,
        increased_limit: Decimal | int | float | str | None = None,
    ):
        super().__init__(
            owner_id=owner_id,
            balance=balance,
            currency=currency,
            account_id=account_id,
            status=status,
        )
        self.overdraft_limit = self._to_decimal(overdraft_limit)
        self.fixed_fee = self._to_decimal(fixed_fee)
        self.increased_limit = (
            self._to_decimal(increased_limit)
            if increased_limit is not None
            else self.overdraft_limit
        )

        if self.fixed_fee < 0:
            raise InvalidOperationError("Fee can\'t be negative")

        if self.overdraft_limit < 0:
            raise InvalidOperationError("Overdraft limit can\'t be negative")

        if self.increased_limit < 0:
            raise InvalidOperationError("Increased limit can\'t be negative")

        if self.balance < -self.overdraft_limit:
            raise InvalidOperationError(
                "Initial balance can\'t be less than overdraft limit"
            )
        

    def withdraw(self, amount: Decimal | int | float | str, apply_fee: bool = True) -> Decimal:
        self._check_status()
        amount = self._validate_amount(amount)

        balance_after = self.balance - amount
        if apply_fee:
            balance_after -= self.fixed_fee
        if balance_after < -self.overdraft_limit:
            raise InsufficientFundsError(
                f"You can't withdraw {amount} {self.currency.value}"
                f"Overdraft limit: {self.overdraft_limit} {self.currency.value}"
            )

        self._balance = balance_after
        return self._balance

    def get_available_funds(self) -> Decimal:
        return self.balance + self.overdraft_limit

    def get_account_info(self) -> dict:
        base_info = super().get_account_info()

        base_info.update(
            {
                "account_type": "PremiumAccount",
                "overdraft_limit": str(self.overdraft_limit),
                "fixed_fee": str(self.fixed_fee),
                "increased_limit": str(self.increased_limit),
                "available_funds": str(self.get_available_funds()),
            }
        )

        return base_info

    def __str__(self):
        return (
            f"Account type: {self.__class__.__name__}\n"
            f"Client: {self.owner_id}\n"
            f"Account ID: ****{str(self.id)[-4:]}\n"
            f"Status: {self.status.value}\n"
            f"Balance: {self._balance} {self.currency.value}\n"
            f"Overdraft limit: {self.overdraft_limit} {self.currency.value}\n"
            f"Fixed fee: {self.fixed_fee} s{self.currency.value}\n"
        )


class InvestmentAccount(BankAccount):
    ALLOWED_ASSETS = {"stocks", "bonds", "etf"}

    DEFAULT_YEARLY_RETURNS = {
        "stocks": Decimal("0.12"), 
        "bonds": Decimal("0.06"),
        "etf": Decimal("0.09")
    }


    def __init__(
        self,
        owner_id: uuid.UUID,
        account_id: uuid.UUID | None = None,
        balance: Decimal | int | float | str = Decimal("0"),
        currency: Currency = Currency.RUB,
        status: AccountStatus = AccountStatus.ACTIVE,
        portfolio: dict[str, Decimal | int | float | str] | None = None,
        yearly_returns: dict[str, Decimal | int | float | str] | None = None,
    ):
        super().__init__(
            owner_id=owner_id,
            balance=balance,
            currency=currency,
            account_id=account_id,
            status=status,
        )
        self.portfolio = self._initialize_portfolio(portfolio)
        self.yearly_returns = self._initialize_yearly_returns(yearly_returns)
        
    def _initialize_portfolio(
        self,
        portfolio: dict[str, Decimal | int | float | str] | None,
    ) -> dict[str, Decimal]:
        result = {
            "stocks": Decimal("0"),
            "bonds": Decimal("0"),
            "etf": Decimal("0"),
        }

        if portfolio is None:
            return result

        for asset, amount in portfolio.items():
            self._validate_asset_type(asset)

            amount = self._to_decimal(amount)

            if amount < 0:
                raise InvalidOperationError(
                    f"Asset {asset} amount can\'t be negative"
                )

            result[asset] = amount

        return result

    def _initialize_yearly_returns(
        self,
        yearly_returns: dict[str, Decimal | int | float | str] | None,
    ) -> dict[str, Decimal]:
        result = self.DEFAULT_YEARLY_RETURNS.copy()

        if yearly_returns is None:
            return result

        for asset, rate in yearly_returns.items():
            self._validate_asset_type(asset)

            rate = self._to_decimal(rate)

            if rate < Decimal("-1"):
                raise InvalidOperationError(
                    "Returns can\'t be less than -100%"
                )

            result[asset] = rate

        return result


    def _validate_asset_type(self, asset: str) -> None:
        if asset not in self.ALLOWED_ASSETS:
            raise InvalidOperationError(
                f"Неизвестный тип актива: {asset}. "
                f"Доступные активы: {', '.join(sorted(self.ALLOWED_ASSETS))}"
            )

    def buy_asset(
        self,
        asset: str,
        amount: Decimal | int | float | str,
    ) -> Decimal:
        self._check_status()
        self._validate_asset_type(asset)

        amount = self._validate_amount(amount)

        if amount > self.balance:
            raise InsufficientFundsError(
                f"Недостаточно средств для покупки актива {asset}"
            )

        self._balance -= amount
        self.portfolio[asset] += amount

        return self.portfolio[asset]

    def invest(
        self,
        asset: str,
        amount: Decimal | int | float | str,
    ) -> Decimal:
        return self.buy_asset(asset, amount)


    def sell_asset(
        self,
        asset: str,
        amount: Decimal | int | float | str,
    ) -> Decimal:
        self._check_status()
        self._validate_asset_type(asset)

        amount = self._validate_amount(amount)

        if amount > self.portfolio[asset]:
            raise InsufficientFundsError(
                f"Недостаточно актива {asset} для продажи"
            )

        self.portfolio[asset] -= amount
        self._balance += amount

        return self._balance


    def withdraw(self, amount: Decimal | int | float | str) -> Decimal:
        return super().withdraw(amount)

    def get_portfolio_value(self) -> Decimal:
        return sum(self.portfolio.values(), Decimal("0"))
    

    def get_total_value(self) -> Decimal:
        return self.balance + self.get_portfolio_value()
    
    def project_yearly_growth(self, years: int = 1) -> dict:
        if years <= 0:
            raise InvalidOperationError("Количество лет должно быть положительным")

        projected_portfolio = {}

        for asset, current_value in self.portfolio.items():
            yearly_return = self.yearly_returns[asset]
            projected_value = current_value * ((Decimal("1") + yearly_return) ** years)

            projected_portfolio[asset] = projected_value.quantize(Decimal("0.01"))

        projected_portfolio_value = sum(
            projected_portfolio.values(),
            Decimal("0"),
        )

        current_portfolio_value = self.get_portfolio_value()
        expected_profit = projected_portfolio_value - current_portfolio_value

        return {
            "years": years,
            "currency": self.currency.value,
            "current_cash_balance": str(self.balance),
            "current_portfolio_value": str(current_portfolio_value),
            "projected_portfolio": {
                asset: str(value)
                for asset, value in projected_portfolio.items()
            },
            "projected_portfolio_value": str(projected_portfolio_value),
            "expected_profit": str(expected_profit.quantize(Decimal("0.01"))),
            "current_total_value": str(self.get_total_value()),
            "projected_total_value": str(
                (self.balance + projected_portfolio_value).quantize(Decimal("0.01"))
            ),
        }

    def get_account_info(self) -> dict:
        base_info = super().get_account_info()

        base_info.update(
            {
                "account_type": "InvestmentAccount",
                "portfolio": {
                    asset: str(amount)
                    for asset, amount in self.portfolio.items()
                },
                "portfolio_value": str(self.get_portfolio_value()),
                "total_value": str(self.get_total_value()),
                "yearly_returns": {
                    asset: str(rate)
                    for asset, rate in self.yearly_returns.items()
                },
            }
        )

        return base_info

    def __str__(self):
        return (
            f"Account type: {self.__class__.__name__}\n"
            f"Client: {self.owner_id}\n"
            f"Account ID: ****{str(self.id)[-4:]}\n"
            f"Status: {self.status.value}\n"
            f"Balance (cash): {self._balance} {self.currency.value}\n"
            f"Balance (portfolio): {self.get_portfolio_value()} {self.currency.value}\n"
            f"Balance (total): {self.get_total_value()} {self.currency.value}\n"
        )
