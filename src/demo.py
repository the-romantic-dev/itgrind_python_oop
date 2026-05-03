from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from models.errors import InvalidOperationError

from models.accounts import BankAccount, InvestmentAccount, PremiumAccount, SavingsAccount

from models.enums import Currency, TransactionStatus, TransactionType
from models.transaction import Transaction

from services.audit_log import AuditLog
from services.bank import Bank
from services.report_builder import ReportBuilder
from services.risk_analyzer import RiskAnalyzer
from services.transaction_processor import TransactionProcessor
from services.transaction_queue import TransactionQueue


OUTPUT_DIR = Path("output")
LOGS_DIR = OUTPUT_DIR / "logs"
REPORTS_DIR = OUTPUT_DIR / "reports"
CHARTS_DIR = OUTPUT_DIR / "charts"

DAYTIME = datetime(2026, 1, 15, 14, 30)
NIGHT_TIME = datetime(2026, 1, 15, 2, 30)
FUTURE_TIME = DAYTIME + timedelta(hours=3)


def print_section(title: str) -> None:
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def print_subsection(title: str) -> None:
    print()
    print("-" * 80)
    print(title)
    print("-" * 80)


def create_services() -> tuple[AuditLog, RiskAnalyzer, Bank, TransactionQueue, TransactionProcessor]:
    audit_log = AuditLog(
        file_path=LOGS_DIR / "audit.json",
        autosave=False,
    )

    risk_analyzer = RiskAnalyzer(
        large_amount_threshold=Decimal("500000"),
        frequent_operations_limit=5,
        frequent_operations_window_seconds=60,
        medium_risk_threshold=40,
        high_risk_threshold=80,
        night_operations_are_high_risk=True,
    )

    bank = Bank(
        name="Python Bank",
        audit_log=audit_log,
        risk_analyzer=risk_analyzer,
        enforce_time_restrictions=False,
    )

    queue = TransactionQueue()

    processor = TransactionProcessor(
        bank=bank,
        audit_log=audit_log,
        risk_analyzer=risk_analyzer,
        max_retries=3,
        external_transfer_fee_rate=Decimal("0.01"),
        external_transfer_min_fee=Decimal("50"),
    )

    return audit_log, risk_analyzer, bank, queue, processor


def create_clients(bank: Bank) -> dict[str, object]:
    clients = {}

    clients["ivan"] = bank.add_client(
        full_name="Ivan Petrov",
        age=25,
        contacts={
            "phone": "+79990000001",
            "email": "ivan@example.com",
        },
        pin="1111",
    )

    clients["anna"] = bank.add_client(
        full_name="Anna Smirnova",
        age=31,
        contacts={
            "phone": "+79990000002",
            "email": "anna@example.com",
        },
        pin="2222",
    )

    clients["petr"] = bank.add_client(
        full_name="Petr Sokolov",
        age=42,
        contacts={
            "phone": "+79990000003",
            "email": "petr@example.com",
        },
        pin="3333",
    )

    clients["maria"] = bank.add_client(
        full_name="Maria Kuznetsova",
        age=29,
        contacts={
            "phone": "+79990000004",
            "email": "maria@example.com",
        },
        pin="4444",
    )

    clients["oleg"] = bank.add_client(
        full_name="Oleg Morozov",
        age=35,
        contacts={
            "phone": "+79990000005",
            "email": "oleg@example.com",
        },
        pin="5555",
    )

    clients["elena"] = bank.add_client(
        full_name="Elena Volkova",
        age=27,
        contacts={
            "phone": "+79990000006",
            "email": "elena@example.com",
        },
        pin="6666",
    )

    return clients


def create_accounts(bank: Bank, clients: dict[str, object]) -> dict[str, object]:
    accounts = {}

    accounts["ivan_base"] = bank.open_account(
        client_id=clients["ivan"].client_id,
        account_type=BankAccount,
        currency=Currency.RUB,
        initial_balance=Decimal("2500000"),
    )

    accounts["ivan_savings"] = bank.open_account(
        client_id=clients["ivan"].client_id,
        account_type=SavingsAccount,
        currency=Currency.RUB,
        initial_balance=Decimal("600000"),
        min_balance=Decimal("100000"),
        monthly_interest_rate=Decimal("0.015"),
    )

    accounts["anna_premium"] = bank.open_account(
        client_id=clients["anna"].client_id,
        account_type=PremiumAccount,
        currency=Currency.RUB,
        initial_balance=Decimal("100000"),
        overdraft_limit=Decimal("200000"),
        fixed_fee=Decimal("100"),
        increased_limit=Decimal("1000000"),
    )

    accounts["anna_investment"] = bank.open_account(
        client_id=clients["anna"].client_id,
        account_type=InvestmentAccount,
        currency=Currency.RUB,
        initial_balance=Decimal("500000"),
    )

    accounts["petr_base"] = bank.open_account(
        client_id=clients["petr"].client_id,
        account_type=BankAccount,
        currency=Currency.USD,
        initial_balance=Decimal("2000"),
    )

    accounts["petr_savings"] = bank.open_account(
        client_id=clients["petr"].client_id,
        account_type=SavingsAccount,
        currency=Currency.RUB,
        initial_balance=Decimal("120000"),
        min_balance=Decimal("30000"),
        monthly_interest_rate=Decimal("0.01"),
    )

    accounts["maria_premium"] = bank.open_account(
        client_id=clients["maria"].client_id,
        account_type=PremiumAccount,
        currency=Currency.RUB,
        initial_balance=Decimal("20000"),
        overdraft_limit=Decimal("100000"),
        fixed_fee=Decimal("150"),
        increased_limit=Decimal("700000"),
    )

    accounts["maria_base"] = bank.open_account(
        client_id=clients["maria"].client_id,
        account_type=BankAccount,
        currency=Currency.RUB,
        initial_balance=Decimal("90000"),
    )

    accounts["oleg_investment"] = bank.open_account(
        client_id=clients["oleg"].client_id,
        account_type=InvestmentAccount,
        currency=Currency.RUB,
        initial_balance=Decimal("300000"),
    )

    accounts["oleg_base"] = bank.open_account(
        client_id=clients["oleg"].client_id,
        account_type=BankAccount,
        currency=Currency.RUB,
        initial_balance=Decimal("70000"),
    )

    accounts["elena_savings"] = bank.open_account(
        client_id=clients["elena"].client_id,
        account_type=SavingsAccount,
        currency=Currency.RUB,
        initial_balance=Decimal("250000"),
        min_balance=Decimal("50000"),
        monthly_interest_rate=Decimal("0.012"),
    )

    accounts["elena_premium"] = bank.open_account(
        client_id=clients["elena"].client_id,
        account_type=PremiumAccount,
        currency=Currency.EUR,
        initial_balance=Decimal("1500"),
        overdraft_limit=Decimal("1000"),
        fixed_fee=Decimal("5"),
        increased_limit=Decimal("50000"),
    )

    accounts["anna_investment"].invest("stocks", Decimal("100000"))
    accounts["anna_investment"].invest("bonds", Decimal("50000"))
    accounts["oleg_investment"].invest("etf", Decimal("75000"))

    accounts["ivan_savings"].apply_monthly_interest()
    accounts["elena_savings"].apply_monthly_interest()

    bank.freeze_account(
        account_id=accounts["maria_base"].account_id,
        reason="Manual demo freeze",
    )

    bank.close_account(
        account_id=accounts["oleg_base"].account_id,
        now=DAYTIME,
        require_zero_balance=False,
    )

    return accounts


def show_authentication_demo(bank: Bank, clients: dict[str, object]) -> None:
    print_section("Authentication demo")

    print("Correct PIN:")
    print(bank.authenticate_client(clients["ivan"].client_id, "1111"))

    print()
    print("Three wrong attempts:")

    for attempt in range(1, 4):
        result = bank.authenticate_client(clients["elena"].client_id, "wrong")
        print(f"Attempt {attempt}: {result}")

    print()
    print(clients["elena"])


def add_transaction(
    queue: TransactionQueue,
    transactions: list[Transaction],
    transaction: Transaction,
) -> Transaction:
    queue.add(transaction)
    transactions.append(transaction)
    return transaction


def create_transactions(
    queue: TransactionQueue,
    accounts: dict[str, object],
) -> list[Transaction]:
    transactions = []

    regular_pairs = [
        ("ivan_base", "anna_premium", "15000"),
        ("ivan_base", "petr_savings", "20000"),
        ("ivan_base", "maria_premium", "25000"),
        ("ivan_base", "oleg_investment", "30000"),
        ("ivan_base", "elena_savings", "35000"),
        ("anna_premium", "ivan_savings", "5000"),
        ("anna_premium", "petr_savings", "7000"),
        ("petr_savings", "maria_premium", "6000"),
        ("maria_premium", "anna_investment", "8000"),
        ("elena_savings", "ivan_base", "9000"),
        ("ivan_base", "anna_premium", "11000"),
        ("ivan_base", "petr_savings", "12000"),
        ("ivan_base", "maria_premium", "13000"),
        ("ivan_base", "oleg_investment", "14000"),
        ("ivan_base", "elena_savings", "15000"),
        ("anna_premium", "ivan_base", "4000"),
        ("petr_savings", "ivan_base", "3000"),
        ("maria_premium", "petr_savings", "3500"),
        ("elena_savings", "anna_premium", "4500"),
        ("ivan_base", "anna_investment", "16000"),
    ]

    for sender_key, receiver_key, amount in regular_pairs:
        add_transaction(
            queue,
            transactions,
            Transaction(
                type=TransactionType.TRANSFER,
                amount=Decimal(amount),
                currency=Currency.RUB,
                sender_account_id=accounts[sender_key].account_id,
                receiver_account_id=accounts[receiver_key].account_id,
                priority=5,
            ),
        )

    deposits = [
        ("ivan_base", "50000"),
        ("anna_premium", "30000"),
        ("petr_base", "500"),
        ("maria_premium", "20000"),
        ("oleg_investment", "40000"),
    ]

    for receiver_key, amount in deposits:
        add_transaction(
            queue,
            transactions,
            Transaction(
                type=TransactionType.DEPOSIT,
                amount=Decimal(amount),
                currency=accounts[receiver_key].currency,
                receiver_account_id=accounts[receiver_key].account_id,
                priority=4,
            ),
        )

    withdrawals = [
        ("ivan_savings", "20000"),
        ("anna_premium", "15000"),
        ("maria_premium", "10000"),
        ("elena_savings", "12000"),
    ]

    for sender_key, amount in withdrawals:
        add_transaction(
            queue,
            transactions,
            Transaction(
                type=TransactionType.WITHDRAW,
                amount=Decimal(amount),
                currency=accounts[sender_key].currency,
                sender_account_id=accounts[sender_key].account_id,
                priority=4,
            ),
        )

    external_transfers = [
        ("ivan_base", "external_card_001", "25000"),
        ("anna_premium", "external_card_002", "10000"),
        ("petr_savings", "external_card_003", "15000"),
    ]

    for sender_key, external_receiver_id, amount in external_transfers:
        add_transaction(
            queue,
            transactions,
            Transaction(
                type=TransactionType.EXTERNAL_TRANSFER,
                amount=Decimal(amount),
                currency=accounts[sender_key].currency,
                sender_account_id=accounts[sender_key].account_id,
                receiver_account_id=external_receiver_id,
                priority=3,
            ),
        )

    failed_cases = [
        Transaction(
            type=TransactionType.WITHDRAW,
            amount=Decimal("9999999"),
            currency=Currency.RUB,
            sender_account_id=accounts["petr_savings"].account_id,
            priority=6,
            metadata={"case": "insufficient_funds"},
        ),
        Transaction(
            type=TransactionType.TRANSFER,
            amount=Decimal("1000"),
            currency=Currency.RUB,
            sender_account_id=accounts["maria_base"].account_id,
            receiver_account_id=accounts["ivan_base"].account_id,
            priority=6,
            metadata={"case": "frozen_sender"},
        ),
        Transaction(
            type=TransactionType.WITHDRAW,
            amount=Decimal("1000"),
            currency=Currency.RUB,
            sender_account_id=accounts["oleg_base"].account_id,
            priority=6,
            metadata={"case": "closed_sender"},
        ),
        Transaction(
            type=TransactionType.TRANSFER,
            amount=Decimal("1000"),
            currency=Currency.RUB,
            sender_account_id=accounts["ivan_base"].account_id,
            receiver_account_id=accounts["ivan_base"].account_id,
            priority=6,
            metadata={"case": "same_sender_receiver"},
        ),
    ]

    for transaction in failed_cases:
        add_transaction(queue, transactions, transaction)

    suspicious_transactions = [
        Transaction(
            type=TransactionType.EXTERNAL_TRANSFER,
            amount=Decimal("600000"),
            currency=Currency.RUB,
            sender_account_id=accounts["ivan_base"].account_id,
            receiver_account_id="external_new_large_001",
            priority=5,
            metadata={"case": "large_external_transfer"},
        ),
        Transaction(
            type=TransactionType.TRANSFER,
            amount=Decimal("650000"),
            currency=Currency.RUB,
            sender_account_id=accounts["ivan_base"].account_id,
            receiver_account_id=accounts["anna_premium"].account_id,
            priority=5,
            metadata={"case": "large_internal_transfer"},
        ),
    ]

    for transaction in suspicious_transactions:
        add_transaction(queue, transactions, transaction)

    delayed_transaction = add_transaction(
        queue,
        transactions,
        Transaction(
            type=TransactionType.TRANSFER,
            amount=Decimal("22000"),
            currency=Currency.RUB,
            sender_account_id=accounts["ivan_base"].account_id,
            receiver_account_id=accounts["petr_savings"].account_id,
            scheduled_at=FUTURE_TIME,
            priority=10,
            metadata={"case": "delayed_transaction"},
        ),
    )

    cancelled_transaction = add_transaction(
        queue,
        transactions,
        Transaction(
            type=TransactionType.TRANSFER,
            amount=Decimal("18000"),
            currency=Currency.RUB,
            sender_account_id=accounts["anna_premium"].account_id,
            receiver_account_id=accounts["maria_premium"].account_id,
            priority=9,
            metadata={"case": "cancelled_transaction"},
        ),
    )

    queue.cancel(cancelled_transaction.transaction_id)

    night_transaction = add_transaction(
        queue,
        transactions,
        Transaction(
            type=TransactionType.TRANSFER,
            amount=Decimal("10000"),
            currency=Currency.RUB,
            sender_account_id=accounts["ivan_base"].account_id,
            receiver_account_id=accounts["anna_premium"].account_id,
            priority=8,
            metadata={"case": "night_transaction"},
        ),
    )

    print(f"Delayed transaction created: {delayed_transaction.transaction_id}")
    print(f"Cancelled transaction created: {cancelled_transaction.transaction_id}")
    print(f"Night transaction created: {night_transaction.transaction_id}")

    return transactions


def process_night_transaction(
    processor: TransactionProcessor,
    transactions: list[Transaction],
) -> None:
    print_section("Night transaction demo")

    night_transaction = next(
        transaction
        for transaction in transactions
        if transaction.metadata.get("case") == "night_transaction"
    )

    processor.bank.enforce_time_restrictions = True
    processor.process(night_transaction, now=NIGHT_TIME)

    print(night_transaction)
    print(f"Failure reason: {night_transaction.failure_reason}")


def process_queue_demo(
    processor: TransactionProcessor,
    queue: TransactionQueue,
) -> None:
    print_section("Queue processing demo")

    processor.bank.enforce_time_restrictions = True

    print("Ready transactions before processing:")
    ready_before = queue.get_ready_transactions(now=DAYTIME)

    for transaction in ready_before[:10]:
        print(transaction)

    if len(ready_before) > 10:
        print(f"... and {len(ready_before) - 10} more")

    print()
    print("Processing daytime queue...")
    processed_now = processor.process_queue(queue, now=DAYTIME)

    print(f"Processed now: {len(processed_now)}")
    print(f"Still active in queue: {len(queue)}")

    print()
    print("Processing delayed transactions...")
    processed_later = processor.process_queue(queue, now=FUTURE_TIME + timedelta(minutes=1))

    print(f"Processed later: {len(processed_later)}")
    print(f"Still active in queue: {len(queue)}")


def print_transaction_summary(transactions: list[Transaction]) -> None:
    print_section("Transaction summary")

    status_counts = {}

    for transaction in transactions:
        status = transaction.status.value
        status_counts[status] = status_counts.get(status, 0) + 1

    for status, count in sorted(status_counts.items()):
        print(f"{status}: {count}")

    print()
    print("Failed / blocked / cancelled transactions:")

    for transaction in transactions:
        if transaction.status in {
            TransactionStatus.FAILED,
            TransactionStatus.BLOCKED,
            TransactionStatus.CANCELLED,
        }:
            print(transaction)
            print(f"Reason: {transaction.failure_reason}")
            print()


def print_bank_state(bank: Bank) -> None:
    print_section("Bank state")

    print(bank)
    print(bank.get_bank_info())

    print_subsection("Total balance by currency")
    print(bank.get_total_balance(convert=False))

    print_subsection("Total balance in RUB")
    print(bank.get_total_balance(base_currency=Currency.RUB))

    print_subsection("Top 3 clients")
    for item in bank.get_clients_ranking(top=3):
        print(item)


def print_clients_and_accounts(bank: Bank, clients: dict[str, object]) -> None:
    print_section("Clients and accounts")

    for client_key, client in clients.items():
        print_subsection(f"{client_key}: {client.full_name}")

        print(client)

        accounts = bank.get_client_accounts(
            client_id=client.client_id,
            include_closed=True,
        )

        for account in accounts:
            print(account)


def print_client_scenario(
    bank: Bank,
    transactions: list[Transaction],
    client,
) -> None:
    print_section(f"Client scenario: {client.full_name}")

    accounts = bank.get_client_accounts(
        client_id=client.client_id,
        include_closed=True,
    )

    account_ids = {
        account.account_id
        for account in accounts
    }

    print_subsection("Accounts")
    for account in accounts:
        print(account)

    print_subsection("Transaction history")
    client_transactions = [
        transaction
        for transaction in transactions
        if transaction.sender_account_id in account_ids
        or transaction.receiver_account_id in account_ids
    ]

    for transaction in client_transactions:
        print(transaction)
        if transaction.failure_reason:
            print(f"Reason: {transaction.failure_reason}")

    print_subsection("Suspicious actions")
    for item in client.suspicious_actions:
        print(item)


def print_audit_and_risk(
    audit_log: AuditLog,
    risk_analyzer: RiskAnalyzer,
) -> None:
    print_section("Audit and risk")

    print_subsection("Suspicious operations from audit")
    suspicious_operations = audit_log.get_suspicious_operations()

    for operation in suspicious_operations[:10]:
        print(operation)

    if len(suspicious_operations) > 10:
        print(f"... and {len(suspicious_operations) - 10} more")

    print_subsection("Error statistics")
    print(audit_log.get_error_statistics())

    print_subsection("Risk statistics")
    print(risk_analyzer.get_statistics())


def generate_reports(
    bank: Bank,
    audit_log: AuditLog,
    risk_analyzer: RiskAnalyzer,
    queue: TransactionQueue,
    sample_client,
) -> None:
    print_section("Reports and charts")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    audit_log.save_to_file(LOGS_DIR / "audit.json")

    report_builder = ReportBuilder(
        bank=bank,
        audit_log=audit_log,
        risk_analyzer=risk_analyzer,
        transactions=queue,
    )

    bank_report = report_builder.build_bank_report()
    risk_report = report_builder.build_risk_report()
    client_report = report_builder.build_client_report(sample_client.client_id)

    report_builder.export_to_json(
        bank_report,
        REPORTS_DIR / "bank_report.json",
    )

    report_builder.export_to_json(
        risk_report,
        REPORTS_DIR / "risk_report.json",
    )

    report_builder.export_to_json(
        client_report,
        REPORTS_DIR / "client_report.json",
    )

    report_builder.export_to_csv(
        bank_report,
        REPORTS_DIR / "bank_report.csv",
    )

    text_report = report_builder.build_text_report(
        title="Bank Report",
        data=bank_report,
    )

    text_report_path = REPORTS_DIR / "bank_report.txt"

    with text_report_path.open("w", encoding="utf-8") as file:
        file.write(text_report)

    saved_charts = {}

    try:
        saved_charts = report_builder.save_charts(CHARTS_DIR)
    except Exception as error:
        print(f"Charts were skipped: {error}")

    print(f"Audit log: {LOGS_DIR / 'audit.json'}")
    print(f"Bank JSON report: {REPORTS_DIR / 'bank_report.json'}")
    print(f"Risk JSON report: {REPORTS_DIR / 'risk_report.json'}")
    print(f"Client JSON report: {REPORTS_DIR / 'client_report.json'}")
    print(f"Bank CSV report: {REPORTS_DIR / 'bank_report.csv'}")
    print(f"Bank text report: {text_report_path}")

    if saved_charts:
        print("Charts:")
        for name, path in saved_charts.items():
            print(f"{name}: {path}")


def main() -> None:
    audit_log, risk_analyzer, bank, queue, processor = create_services()

    print_section("Creating clients")
    clients = create_clients(bank)

    for client in clients.values():
        print(client)

    print_section("Creating accounts")
    accounts = create_accounts(bank, clients)

    for account in accounts.values():
        print(account)

    show_authentication_demo(bank, clients)

    print_section("Creating transactions")
    transactions = create_transactions(queue, accounts)

    print(f"Transactions created: {len(transactions)}")
    print(f"Active transactions in queue: {len(queue)}")

    process_night_transaction(processor, transactions)
    process_queue_demo(processor, queue)

    print_transaction_summary(transactions)
    print_bank_state(bank)
    print_clients_and_accounts(bank, clients)

    print_client_scenario(
        bank=bank,
        transactions=transactions,
        client=clients["ivan"],
    )

    print_audit_and_risk(
        audit_log=audit_log,
        risk_analyzer=risk_analyzer,
    )

    generate_reports(
        bank=bank,
        audit_log=audit_log,
        risk_analyzer=risk_analyzer,
        queue=queue,
        sample_client=clients["ivan"],
    )

    print_section("Demo completed")


if __name__ == "__main__":
    main()