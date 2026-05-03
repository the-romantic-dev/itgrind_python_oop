from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import matplotlib
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

matplotlib.use("Agg")

from models.accounts import (  # noqa: E402
    BankAccount,
    InvestmentAccount,
    PremiumAccount,
    SavingsAccount,
)
from models.enums import AccountStatus, ClientStatus, Currency, TransactionStatus, TransactionType  # noqa: E402
from models.errors import (  # noqa: E402
    AccountClosedError,
    AccountFrozenError,
    ClientBlockedError,
    InsufficientFundsError,
    InvalidOperationError,
)
from models.transaction import Transaction  # noqa: E402
from services.audit_log import AuditLog  # noqa: E402
from services.bank import Bank  # noqa: E402
from services.report_builder import ReportBuilder  # noqa: E402
from services.risk_analyzer import RiskAnalyzer  # noqa: E402
from services.transaction_processor import TransactionProcessor  # noqa: E402
from services.transaction_queue import TransactionQueue  # noqa: E402


DAYTIME = datetime(2026, 1, 15, 14, 30)
NIGHT_TIME = datetime(2026, 1, 15, 2, 30)


@pytest.fixture
def audit_log() -> AuditLog:
    return AuditLog(autosave=False)


@pytest.fixture
def bank(audit_log: AuditLog) -> Bank:
    return Bank(
        name="Test Bank",
        audit_log=audit_log,
        risk_analyzer=None,
        enforce_time_restrictions=False,
    )


@pytest.fixture
def clients(bank: Bank) -> dict[str, object]:
    return {
        "sender": bank.add_client(
            full_name="Sender Client",
            age=30,
            contacts={"email": "sender@example.com"},
            pin="1111",
        ),
        "receiver": bank.add_client(
            full_name="Receiver Client",
            age=34,
            contacts={"email": "receiver@example.com"},
            pin="2222",
        ),
    }


def test_bank_account_validates_status_amounts_and_string_representation() -> None:
    owner_id = uuid4()
    account = BankAccount(
        owner_id=owner_id,
        balance=Decimal("100.50"),
        currency=Currency.RUB,
    )

    account.deposit("49.50")
    account.withdraw(Decimal("25"))

    info = account.get_account_info()

    assert isinstance(account.account_id, UUID)
    assert account.balance == Decimal("125.00")
    assert info["account_type"] == "BankAccount"
    assert info["owner_id"] == str(owner_id)
    assert info["balance"] == "125.00"
    assert info["currency"] == "RUB"
    assert str(account.account_id)[-4:] in str(account)

    with pytest.raises(InvalidOperationError):
        account.deposit(0)

    with pytest.raises(InvalidOperationError):
        account.withdraw("-1")

    with pytest.raises(InsufficientFundsError):
        account.withdraw("1000")

    frozen = BankAccount(owner_id=owner_id, balance=10, status=AccountStatus.FROZEN)
    closed = BankAccount(owner_id=owner_id, balance=10, status=AccountStatus.CLOSED)

    with pytest.raises(AccountFrozenError):
        frozen.deposit(1)

    with pytest.raises(AccountClosedError):
        closed.withdraw(1)


def test_savings_premium_and_investment_accounts_extend_base_behaviour() -> None:
    owner_id = uuid4()

    savings = SavingsAccount(
        owner_id=owner_id,
        balance=1000,
        min_balance=500,
        monthly_interest_rate=Decimal("0.01"),
    )
    savings.withdraw(400)

    assert savings.balance == Decimal("600")

    with pytest.raises(InsufficientFundsError):
        savings.withdraw(101)

    assert savings.apply_monthly_interest() == Decimal("6.00")
    assert savings.get_account_info()["monthly_interest_rate"] == "0.01"

    premium = PremiumAccount(
        owner_id=owner_id,
        balance=100,
        overdraft_limit=50,
        fixed_fee=10,
        increased_limit=100000,
    )
    premium.withdraw(120)

    assert premium.balance == Decimal("-30")
    assert premium.get_available_funds() == Decimal("20")

    with pytest.raises(InsufficientFundsError):
        premium.withdraw(11)

    premium_info = premium.get_account_info()
    assert premium_info["fixed_fee"] == "10"
    assert premium_info["increased_limit"] == "100000"

    investment = InvestmentAccount(owner_id=owner_id, balance=1000)
    investment.invest("stocks", 200)
    investment.sell_asset("stocks", 50)

    projection = investment.project_yearly_growth(years=1)

    assert investment.balance == Decimal("850")
    assert investment.portfolio["stocks"] == Decimal("150")
    assert projection["expected_profit"] == "18.00"
    assert investment.get_account_info()["total_value"] == "1000"

    with pytest.raises(InvalidOperationError):
        InvestmentAccount(owner_id=owner_id, portfolio={"crypto": 100})


def test_bank_manages_clients_accounts_authentication_and_rankings(audit_log: AuditLog) -> None:
    secure_bank = Bank(
        name="Secure Bank",
        audit_log=audit_log,
        risk_analyzer=None,
        enforce_time_restrictions=True,
    )

    client = secure_bank.add_client(
        full_name="Adult Client",
        age=40,
        contacts={"phone": "+70000000000"},
        pin="1234",
    )
    second_client = secure_bank.add_client(
        full_name="Second Client",
        age=25,
        pin="4321",
    )

    account = secure_bank.open_account(
        client_id=client.client_id,
        account_type=BankAccount,
        currency=Currency.RUB,
        initial_balance=5000,
        now=DAYTIME,
    )
    secure_bank.open_account(
        client_id=second_client.client_id,
        account_type=BankAccount,
        currency=Currency.USD,
        initial_balance=10,
        now=DAYTIME,
    )

    assert secure_bank.authenticate_client(client.client_id, "1234") is True
    assert secure_bank.search_accounts(client_id=client.client_id) == [account]
    assert secure_bank.get_total_balance(base_currency=Currency.RUB) == Decimal("5900.00")
    assert secure_bank.get_clients_ranking(top=1)[0]["client_id"] == str(client.client_id)

    secure_bank.freeze_account(account.account_id, reason="test")
    assert account.status == AccountStatus.FROZEN
    secure_bank.unfreeze_account(account.account_id, reason="test")
    assert account.status == AccountStatus.ACTIVE

    for _ in range(3):
        assert secure_bank.authenticate_client(second_client.client_id, "wrong") is False

    assert second_client.status == ClientStatus.BLOCKED

    with pytest.raises(ClientBlockedError):
        secure_bank.authenticate_client(second_client.client_id, "4321")

    with pytest.raises(InvalidOperationError):
        secure_bank.open_account(
            client_id=client.client_id,
            account_type=BankAccount,
            now=NIGHT_TIME,
        )


def test_transaction_queue_orders_ready_transactions_and_supports_cancellation() -> None:
    queue = TransactionQueue()
    now = DAYTIME

    low_priority = Transaction(
        type=TransactionType.DEPOSIT,
        amount=10,
        receiver_account_id="receiver",
        priority=1,
        created_at=now,
    )
    high_priority = Transaction(
        type=TransactionType.DEPOSIT,
        amount=10,
        receiver_account_id="receiver",
        priority=10,
        created_at=now + timedelta(seconds=1),
    )
    delayed = Transaction(
        type=TransactionType.DEPOSIT,
        amount=10,
        receiver_account_id="receiver",
        priority=100,
        scheduled_at=now + timedelta(hours=1),
    )
    cancelled = Transaction(
        type=TransactionType.DEPOSIT,
        amount=10,
        receiver_account_id="receiver",
        priority=50,
    )

    for transaction in (low_priority, high_priority, delayed, cancelled):
        queue.add(transaction)

    queue.cancel(cancelled.transaction_id)

    ready_now = queue.get_ready_transactions(now=now)
    ready_later = queue.get_ready_transactions(now=now + timedelta(hours=2))

    assert ready_now == [high_priority, low_priority]
    assert ready_later[:3] == [delayed, high_priority, low_priority]
    assert cancelled.status == TransactionStatus.CANCELLED
    assert len(queue) == 3


def test_transaction_processor_handles_money_movement_fees_conversion_and_failures(
    bank: Bank,
    clients: dict[str, object],
    audit_log: AuditLog,
) -> None:
    sender = bank.open_account(
        client_id=clients["sender"].client_id,
        account_type=BankAccount,
        currency=Currency.RUB,
        initial_balance=5000,
    )
    receiver_usd = bank.open_account(
        client_id=clients["receiver"].client_id,
        account_type=BankAccount,
        currency=Currency.USD,
        initial_balance=0,
    )
    receiver_rub = bank.open_account(
        client_id=clients["receiver"].client_id,
        account_type=BankAccount,
        currency=Currency.RUB,
        initial_balance=100,
    )
    processor = TransactionProcessor(
        bank=bank,
        audit_log=audit_log,
        risk_analyzer=None,
        external_transfer_fee_rate=Decimal("0.01"),
        external_transfer_min_fee=Decimal("50"),
    )

    deposit = Transaction(
        type=TransactionType.DEPOSIT,
        amount=100,
        currency=Currency.RUB,
        receiver_account_id=receiver_rub.account_id,
    )
    transfer = Transaction(
        type=TransactionType.TRANSFER,
        amount=90,
        currency=Currency.RUB,
        sender_account_id=sender.account_id,
        receiver_account_id=receiver_usd.account_id,
    )
    external = Transaction(
        type=TransactionType.EXTERNAL_TRANSFER,
        amount=1000,
        currency=Currency.RUB,
        sender_account_id=sender.account_id,
        receiver_account_id="external-card",
    )

    processor.process(deposit, now=DAYTIME)
    processor.process(transfer, now=DAYTIME)
    processor.process(external, now=DAYTIME)

    assert deposit.status == TransactionStatus.COMPLETED
    assert transfer.status == TransactionStatus.COMPLETED
    assert external.status == TransactionStatus.COMPLETED
    assert receiver_rub.balance == Decimal("200")
    assert receiver_usd.balance == Decimal("1.00")
    assert external.fee == Decimal("50.00")
    assert sender.balance == Decimal("3860.00")

    bank.freeze_account(sender.account_id, reason="test")

    failed = Transaction(
        type=TransactionType.WITHDRAW,
        amount=1,
        currency=Currency.RUB,
        sender_account_id=sender.account_id,
    )
    processor.process(failed, now=DAYTIME)

    assert failed.status == TransactionStatus.FAILED
    assert "frozen" in failed.failure_reason.lower()
    assert audit_log.get_error_statistics()["total_errors"] == 1


def test_risk_analyzer_blocks_high_risk_transactions_and_records_profile(
    audit_log: AuditLog,
) -> None:
    risk_analyzer = RiskAnalyzer(
        large_amount_threshold=Decimal("100"),
        medium_risk_threshold=20,
        high_risk_threshold=40,
        night_operations_are_high_risk=True,
    )
    risky_bank = Bank(
        name="Risk Bank",
        audit_log=audit_log,
        risk_analyzer=risk_analyzer,
        enforce_time_restrictions=False,
    )
    client = risky_bank.add_client("Risky Client", age=30, pin="1234")
    account = risky_bank.open_account(client.client_id, BankAccount, initial_balance=1000)
    processor = TransactionProcessor(
        bank=risky_bank,
        audit_log=audit_log,
        risk_analyzer=risk_analyzer,
    )
    transaction = Transaction(
        type=TransactionType.EXTERNAL_TRANSFER,
        amount=150,
        sender_account_id=account.account_id,
        receiver_account_id="new-external-receiver",
    )

    processor.process(transaction, now=DAYTIME)

    assert transaction.status == TransactionStatus.BLOCKED
    assert account.balance == Decimal("1000")
    assert risk_analyzer.get_statistics()["high"] == 1
    assert risk_analyzer.get_client_risk_profile(client.client_id)["high"] == 1
    assert audit_log.get_suspicious_operations()


def test_report_builder_exports_reports_and_charts(
    tmp_path: Path,
    bank: Bank,
    clients: dict[str, object],
    audit_log: AuditLog,
) -> None:
    sender = bank.open_account(
        client_id=clients["sender"].client_id,
        account_type=BankAccount,
        currency=Currency.RUB,
        initial_balance=1000,
    )
    receiver = bank.open_account(
        client_id=clients["receiver"].client_id,
        account_type=BankAccount,
        currency=Currency.RUB,
        initial_balance=0,
    )
    transaction = Transaction(
        type=TransactionType.TRANSFER,
        amount=100,
        sender_account_id=sender.account_id,
        receiver_account_id=receiver.account_id,
    )
    processor = TransactionProcessor(bank=bank, audit_log=audit_log, risk_analyzer=None)
    processor.process(transaction, now=DAYTIME)

    report_builder = ReportBuilder(
        bank=bank,
        audit_log=audit_log,
        risk_analyzer=None,
        transactions=[transaction],
    )

    bank_report = report_builder.build_bank_report()
    client_report = report_builder.build_client_report(clients["sender"].client_id)
    risk_report = report_builder.build_risk_report()

    json_path = report_builder.export_to_json(bank_report, tmp_path / "bank.json")
    csv_path = report_builder.export_to_csv(bank_report, tmp_path / "bank.csv")
    text = report_builder.build_text_report("Bank Report", bank_report)
    charts = report_builder.save_charts(tmp_path / "charts")

    with json_path.open(encoding="utf-8") as file:
        saved_json = json.load(file)

    with csv_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert bank_report["transaction_statistics"]["completed"] == 1
    assert client_report["client"]["client_id"] == str(clients["sender"].client_id)
    assert risk_report["report_type"] == "risk"
    assert saved_json["report_type"] == "bank"
    assert rows
    assert "Bank Report" in text
    assert set(charts) == {
        "transaction_statuses",
        "clients_balance",
        "balance_movement",
    }
    assert all(Path(path).exists() and Path(path).stat().st_size > 0 for path in charts.values())
