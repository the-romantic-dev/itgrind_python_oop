import pytest
from src.hw_day1.main import AccountFrozenError, AccountStatus, BankAccount, InsufficientFundsError, InvalidOperationError, PersonalData
from datetime import date

@pytest.fixture
def personal_data():
    return PersonalData(
        first_name='Abobus',
        last_name='Abobusov',
        middle_name='Abobusovich',
        brith_date=date.fromisoformat('2002-02-02')
    )

def test_account_creation(personal_data):
    active_account = BankAccount(
        personal_data = personal_data,
        currency='RUB',
        status=AccountStatus.ACTIVE
    )
    print(str(active_account))
    assert active_account.status == AccountStatus.ACTIVE

    frozen_account = BankAccount(
        personal_data = personal_data,
        currency='RUB',
        status=AccountStatus.FROZEN
    )

    assert frozen_account.status == AccountStatus.FROZEN

def test_operations(personal_data):
    active_account = BankAccount(
        personal_data = personal_data,
        currency='RUB',
        status=AccountStatus.ACTIVE
    )
    active_account.deposit(10)

    assert active_account.get_account_info()['balance'] == 10.0

    active_account.withdraw(5)

    assert active_account.get_account_info()['balance'] == 5.0

    with pytest.raises(InsufficientFundsError):
        active_account.withdraw(10)

    with pytest.raises(InvalidOperationError):
        active_account.withdraw(-5)

def test_frozen_operations(personal_data):
    frozen_account = BankAccount(
        personal_data = personal_data,
        currency='RUB',
        status=AccountStatus.FROZEN,
        init_balance=10.0
    )

    with pytest.raises(AccountFrozenError):
        frozen_account.deposit(10)

    with pytest.raises(AccountFrozenError):
        frozen_account.withdraw(5)