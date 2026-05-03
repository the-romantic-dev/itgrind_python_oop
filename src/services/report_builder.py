from __future__ import annotations

import csv
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from models.enums import Currency, TransactionStatus, TransactionType
from models.errors import InvalidOperationError



class ReportBuilder:
    def __init__(
        self,
        bank,
        audit_log=None,
        risk_analyzer=None,
        transactions=None,
    ):
        self.bank = bank
        self.audit_log = audit_log if audit_log is not None else getattr(bank, "audit_log", None)
        self.risk_analyzer = risk_analyzer if risk_analyzer is not None else getattr(bank, "risk_analyzer", None)
        self.transactions = transactions

    def build_client_report(self, client_id: str) -> dict:
        client = self.bank._get_client_or_raise(client_id)
        accounts = self.bank.get_client_accounts(client_id, include_closed=True)
        account_ids = {account.account_id for account in accounts}

        client_transactions = [
            transaction
            for transaction in self._get_transactions()
            if transaction.sender_account_id in account_ids
            or transaction.receiver_account_id in account_ids
        ]

        risk_profile = None

        if self.risk_analyzer is not None:
            risk_profile = self.risk_analyzer.get_client_risk_profile(client_id)

        audit_profile = None

        if self.audit_log is not None:
            audit_profile = self.audit_log.get_client_risk_profile(client_id)

        return {
            "report_type": "client",
            "created_at": datetime.now().isoformat(),
            "client": client.get_client_info(),
            "accounts": [
                account.get_account_info()
                for account in accounts
            ],
            "transactions": [
                self._transaction_to_dict(transaction)
                for transaction in client_transactions
            ],
            "total_balance_rub": str(
                self._calculate_accounts_total(accounts, Currency.RUB)
            ),
            "risk_profile": risk_profile,
            "audit_profile": audit_profile,
        }

    def build_bank_report(self) -> dict:
        transactions = self._get_transactions()

        return {
            "report_type": "bank",
            "created_at": datetime.now().isoformat(),
            "bank": self.bank.get_bank_info(),
            "total_balance_rub": str(
                self.bank.get_total_balance(base_currency=Currency.RUB)
            ),
            "balances_by_currency": self.bank.get_total_balance(convert=False),
            "clients_ranking_top_3": self.bank.get_clients_ranking(top=3),
            "transaction_statistics": self._get_transaction_statistics(transactions),
            "accounts_count_by_type": self._get_accounts_count_by_type(),
            "accounts_count_by_status": self._get_accounts_count_by_status(),
        }

    def build_risk_report(self) -> dict:
        suspicious_operations = []

        if self.audit_log is not None:
            suspicious_operations = self.audit_log.get_suspicious_operations()

        risk_statistics = None
        risk_assessments = []

        if self.risk_analyzer is not None:
            risk_statistics = self.risk_analyzer.get_statistics()
            risk_assessments = [
                assessment.to_dict()
                for assessment in self.risk_analyzer.get_suspicious_assessments()
            ]

        return {
            "report_type": "risk",
            "created_at": datetime.now().isoformat(),
            "risk_statistics": risk_statistics,
            "risk_assessments": risk_assessments,
            "suspicious_operations_from_audit": suspicious_operations,
            "error_statistics": (
                self.audit_log.get_error_statistics()
                if self.audit_log is not None
                else None
            ),
        }

    def build_text_report(
        self,
        title: str,
        data: dict,
    ) -> str:
        lines = [
            title,
            "=" * len(title),
            f"Created at: {datetime.now().isoformat()}",
            "",
        ]

        self._append_text_lines(lines, data)

        return "\n".join(lines)

    def export_to_json(
        self,
        data: dict | list,
        file_path: str | Path,
    ) -> Path:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", encoding="utf-8") as file:
            json.dump(
                self._make_json_safe(data),
                file,
                ensure_ascii=False,
                indent=4,
            )

        return path

    def export_to_csv(
        self,
        data: dict | list[dict],
        file_path: str | Path,
    ) -> Path:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        rows = self._prepare_csv_rows(data)

        if not rows:
            raise InvalidOperationError("No data to export")

        fieldnames = sorted(
            {
                key
                for row in rows
                for key in row.keys()
            }
        )

        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()

            for row in rows:
                writer.writerow(
                    {
                        key: self._stringify_csv_value(row.get(key))
                        for key in fieldnames
                    }
                )

        return path

    def save_charts(
        self,
        output_dir: str | Path,
    ) -> dict[str, str]:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        saved_files = {}

        status_chart = self.save_transaction_status_pie(
            output_dir / "transaction_statuses.png"
        )

        if status_chart is not None:
            saved_files["transaction_statuses"] = str(status_chart)

        clients_chart = self.save_clients_balance_bar(
            output_dir / "clients_balance.png"
        )

        if clients_chart is not None:
            saved_files["clients_balance"] = str(clients_chart)

        balance_chart = self.save_balance_movement_chart(
            output_dir / "balance_movement.png"
        )

        if balance_chart is not None:
            saved_files["balance_movement"] = str(balance_chart)

        return saved_files

    def save_transaction_status_pie(
        self,
        file_path: str | Path,
    ) -> Path | None:
        import matplotlib.pyplot as plt

        statistics = self._get_transaction_status_counts()

        if not statistics:
            return None

        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        labels = list(statistics.keys())
        values = list(statistics.values())

        plt.figure()
        plt.pie(values, labels=labels, autopct="%1.1f%%")
        plt.title("Transaction statuses")
        plt.savefig(path)
        plt.close()

        return path

    def save_clients_balance_bar(
        self,
        file_path: str | Path,
    ) -> Path | None:
        import matplotlib.pyplot as plt

        ranking = self.bank.get_clients_ranking()

        if not ranking:
            return None

        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        names = [
            item["full_name"]
            for item in ranking
        ]

        balances = [
            float(item["total_balance"])
            for item in ranking
        ]

        plt.figure()
        plt.bar(names, balances)
        plt.title("Clients balance ranking")
        plt.xlabel("Client")
        plt.ylabel("Balance, RUB")
        plt.xticks(rotation=30, ha="right")
        plt.tight_layout()
        plt.savefig(path)
        plt.close()

        return path

    def save_balance_movement_chart(
        self,
        file_path: str | Path,
        account_id: str | None = None,
    ) -> Path | None:
        import matplotlib.pyplot as plt

        transactions = [
            transaction
            for transaction in self._get_transactions()
            if self._is_completed(transaction)
        ]

        if account_id is not None:
            transactions = [
                transaction
                for transaction in transactions
                if transaction.sender_account_id == account_id
                or transaction.receiver_account_id == account_id
            ]

        if not transactions:
            return None

        transactions.sort(
            key=lambda transaction: transaction.processed_at or transaction.created_at
        )

        timestamps = []
        values = []
        current_value = Decimal("0")

        for transaction in transactions:
            delta = self._get_transaction_delta(
                transaction=transaction,
                account_id=account_id,
            )

            current_value += delta

            timestamps.append(transaction.processed_at or transaction.created_at)
            values.append(float(current_value))

        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        plt.figure()
        plt.plot(timestamps, values, marker="o")
        plt.title("Balance movement")
        plt.xlabel("Time")
        plt.ylabel("Cumulative change")
        plt.xticks(rotation=30, ha="right")
        plt.tight_layout()
        plt.savefig(path)
        plt.close()

        return path

    def _get_transactions(self) -> list:
        if self.transactions is None:
            return []

        if isinstance(self.transactions, list):
            return self.transactions

        if hasattr(self.transactions, "get_all_transactions"):
            return self.transactions.get_all_transactions()

        raise InvalidOperationError("Invalid transactions source")

    def _transaction_to_dict(self, transaction) -> dict:
        if hasattr(transaction, "to_dict"):
            return transaction.to_dict()

        return dict(transaction.__dict__)

    def _get_transaction_statistics(self, transactions: list) -> dict:
        statistics = {
            "total": len(transactions),
            "by_status": {},
            "by_type": {},
            "failed": 0,
            "completed": 0,
            "blocked": 0,
        }

        for transaction in transactions:
            status = self._enum_value(transaction.status)
            tx_type = self._enum_value(transaction.type)

            statistics["by_status"][status] = (
                statistics["by_status"].get(status, 0) + 1
            )

            statistics["by_type"][tx_type] = (
                statistics["by_type"].get(tx_type, 0) + 1
            )

            if status == TransactionStatus.FAILED.value:
                statistics["failed"] += 1

            elif status == TransactionStatus.COMPLETED.value:
                statistics["completed"] += 1

            elif status == TransactionStatus.BLOCKED.value:
                statistics["blocked"] += 1

        return statistics

    def _get_transaction_status_counts(self) -> dict[str, int]:
        counts = {}

        for transaction in self._get_transactions():
            status = self._enum_value(transaction.status)
            counts[status] = counts.get(status, 0) + 1

        return counts

    def _get_accounts_count_by_type(self) -> dict[str, int]:
        counts = {}

        for account in self.bank.accounts.values():
            account_type = account.__class__.__name__
            counts[account_type] = counts.get(account_type, 0) + 1

        return counts

    def _get_accounts_count_by_status(self) -> dict[str, int]:
        counts = {}

        for account in self.bank.accounts.values():
            status = self._enum_value(account.status)
            counts[status] = counts.get(status, 0) + 1

        return counts

    def _calculate_accounts_total(
        self,
        accounts: list,
        currency: Currency,
    ) -> Decimal:
        total = Decimal("0")

        for account in accounts:
            total += self.bank._convert_to_currency(
                amount=account.balance,
                from_currency=account.currency,
                to_currency=currency,
            )

        return total.quantize(Decimal("0.01"))

    def _get_transaction_delta(
        self,
        transaction,
        account_id: str | None = None,
    ) -> Decimal:
        amount = Decimal(str(transaction.amount))
        fee = Decimal(str(transaction.fee))

        if account_id is not None:
            if transaction.receiver_account_id == account_id:
                return amount

            if transaction.sender_account_id == account_id:
                return -(amount + fee)

            return Decimal("0")

        if transaction.type == TransactionType.DEPOSIT:
            return amount

        if transaction.type in {
            TransactionType.WITHDRAW,
            TransactionType.EXTERNAL_TRANSFER,
        }:
            return -(amount + fee)

        return Decimal("0")

    @staticmethod
    def _is_completed(transaction) -> bool:
        status = transaction.status

        if hasattr(status, "value"):
            return status.value == TransactionStatus.COMPLETED.value

        return str(status) == TransactionStatus.COMPLETED.value

    @staticmethod
    def _enum_value(value) -> str:
        if hasattr(value, "value"):
            return value.value

        return str(value)

    def _prepare_csv_rows(
        self,
        data: dict | list[dict],
    ) -> list[dict]:
        if isinstance(data, list):
            return [
                self._flatten_dict(row)
                for row in data
            ]

        if isinstance(data, dict):
            flattened = self._flatten_dict(data)

            return [
                {
                    "key": key,
                    "value": value,
                }
                for key, value in flattened.items()
            ]

        raise InvalidOperationError("CSV export supports only dict or list of dicts")

    def _flatten_dict(
        self,
        data: dict,
        parent_key: str = "",
    ) -> dict:
        result = {}

        for key, value in data.items():
            new_key = f"{parent_key}.{key}" if parent_key else str(key)

            if isinstance(value, dict):
                result.update(self._flatten_dict(value, new_key))
            else:
                result[new_key] = value

        return result

    def _append_text_lines(
        self,
        lines: list[str],
        data,
        indent: int = 0,
    ) -> None:
        prefix = " " * indent

        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    lines.append(f"{prefix}{key}:")
                    self._append_text_lines(lines, value, indent + 2)
                else:
                    lines.append(f"{prefix}{key}: {value}")

        elif isinstance(data, list):
            for index, item in enumerate(data, start=1):
                lines.append(f"{prefix}- item {index}:")
                self._append_text_lines(lines, item, indent + 2)

        else:
            lines.append(f"{prefix}{data}")

    @staticmethod
    def _make_json_safe(data):
        if isinstance(data, dict):
            return {
                key: ReportBuilder._make_json_safe(value)
                for key, value in data.items()
            }

        if isinstance(data, list):
            return [
                ReportBuilder._make_json_safe(value)
                for value in data
            ]

        if isinstance(data, Decimal):
            return str(data)

        if isinstance(data, datetime):
            return data.isoformat()

        if isinstance(data, UUID):
            return str(data)

        if hasattr(data, "value"):
            return data.value

        return data

    @staticmethod
    def _stringify_csv_value(value) -> str:
        if isinstance(value, (dict, list)):
            return json.dumps(
                ReportBuilder._make_json_safe(value),
                ensure_ascii=False,
            )

        if isinstance(value, Decimal):
            return str(value)

        if isinstance(value, UUID):
            return str(value)

        if value is None:
            return ""

        return str(value)
