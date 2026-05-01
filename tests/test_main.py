from datetime import date

import pytest

from src.main import (
    AccountClosedError,
    AccountFrozenError,
    AccountStatus,
    BankAccount,
    Currency,
    InsufficientFundsError,
    InvalidOperationError,
    InvestmentAccount,
    PersonalData,
    PremiumAccount,
    SavingsAccount,
)


@pytest.fixture
def personal_data():
    return PersonalData(
        first_name="Abobus",
        last_name="Abobusov",
        middle_name="Abobusovich",
        brith_date=date.fromisoformat("2002-02-02"),
    )


def test_account_creation_uses_enum_currency(personal_data):
    account = BankAccount(
        personal_data=personal_data,
        currency=Currency.RUB,
        status=AccountStatus.ACTIVE,
    )

    info = account.get_account_info()

    assert account.status == AccountStatus.ACTIVE
    assert info["currency"] == Currency.RUB
    assert info["balance"] == 0.0
    assert str(account.id)[-4:] in str(account)


def test_bank_account_operations(personal_data):
    account = BankAccount(
        personal_data=personal_data,
        currency=Currency.RUB,
        status=AccountStatus.ACTIVE,
    )

    account.deposit(10)
    account.withdraw(5)

    assert account.get_account_info()["balance"] == 5.0

    with pytest.raises(InsufficientFundsError):
        account.withdraw(10)
    with pytest.raises(InvalidOperationError):
        account.withdraw(-5)
    with pytest.raises(InvalidOperationError):
        account.deposit(0)
    with pytest.raises(InvalidOperationError):
        account.withdraw(account.withdrawal_limit + 1)


def test_frozen_and_closed_accounts_block_operations(personal_data):
    frozen_account = BankAccount(
        personal_data=personal_data,
        currency=Currency.RUB,
        status=AccountStatus.FROZEN,
        init_balance=10.0,
    )
    closed_account = BankAccount(
        personal_data=personal_data,
        currency=Currency.USD,
        status=AccountStatus.CLOSED,
        init_balance=10.0,
    )

    with pytest.raises(AccountFrozenError):
        frozen_account.deposit(10)
    with pytest.raises(AccountFrozenError):
        frozen_account.withdraw(5)
    with pytest.raises(AccountClosedError):
        closed_account.deposit(10)
    with pytest.raises(AccountClosedError):
        closed_account.withdraw(5)


def test_invalid_initial_balance_is_rejected(personal_data):
    with pytest.raises(InvalidOperationError):
        BankAccount(
            personal_data=personal_data,
            currency=Currency.RUB,
            status=AccountStatus.ACTIVE,
            init_balance=-1,
        )


def test_savings_account_min_balance_and_interest(personal_data):
    account = SavingsAccount(
        personal_data=personal_data,
        currency=Currency.EUR,
        status=AccountStatus.ACTIVE,
        min_balance=500,
        monthly_interest=0.01,
        init_balance=1_000,
    )

    account.withdraw(400)
    assert account.get_account_info()["balance"] == 600

    with pytest.raises(InsufficientFundsError):
        account.withdraw(101)

    account.apply_monthly_interest()
    assert account.get_account_info()["balance"] == pytest.approx(606)
    assert "Minimum balance" in str(account)


def test_premium_account_withdraws_fee_and_allows_overdraft(personal_data):
    account = PremiumAccount(
        personal_data=personal_data,
        currency=Currency.USD,
        status=AccountStatus.ACTIVE,
        withdrawal_fee=10,
        overdraft_limit=50,
        init_balance=100,
    )

    account.withdraw(120)
    info = account.get_account_info()

    assert info["balance"] == -30
    assert info["withdrawal_limit"] == 100_000.0
    assert info["withdrawal_fee"] == 10
    assert info["overdraft_limit"] == 50

    with pytest.raises(InsufficientFundsError):
        account.withdraw(20)
    with pytest.raises(InvalidOperationError):
        account.withdraw(account.withdrawal_limit + 1)
    assert "Overdraft limit" in str(account)


def test_investment_account_portfolio_and_growth_projection(personal_data):
    account = InvestmentAccount(
        personal_data=personal_data,
        currency=Currency.CNY,
        status=AccountStatus.ACTIVE,
        init_balance=1_000,
        portfolio={
            "stocks": 1_000,
            "bonds": 2_000,
            "etf": 500,
        },
        yearly_growth_rates={
            "stocks": 0.10,
            "bonds": 0.05,
            "etf": 0.08,
        },
    )

    account.withdraw(250)
    info = account.get_account_info()

    assert info["balance"] == 750
    assert account.project_yearly_growth() == pytest.approx(240)
    assert info["projected_yearly_growth"] == pytest.approx(240)
    assert info["portfolio"]["stocks"] == 1_000
    assert "Projected yearly growth" in str(account)


def test_investment_account_rejects_unknown_assets(personal_data):
    with pytest.raises(InvalidOperationError):
        InvestmentAccount(
            personal_data=personal_data,
            currency=Currency.KZT,
            status=AccountStatus.ACTIVE,
            portfolio={"crypto": 100},
        )


def test_advanced_accounts_override_polymorphic_methods():
    for account_type in (SavingsAccount, PremiumAccount, InvestmentAccount):
        assert "withdraw" in account_type.__dict__
        assert "get_account_info" in account_type.__dict__
        assert "__str__" in account_type.__dict__
