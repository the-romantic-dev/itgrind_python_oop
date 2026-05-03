from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from models.enums import RiskLevel, TransactionType
from models.transaction import Transaction
from models.errors import InvalidOperationError

@dataclass
class RiskAssessment:
    transaction_id: str
    level: RiskLevel
    score: int
    reasons: list[str]
    client_id: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    assessment_id: str = field(default_factory=lambda: f"risk_{uuid4().hex[:10]}")

    def to_dict(self) -> dict:
        return {
            "assessment_id": self.assessment_id,
            "transaction_id": self.transaction_id,
            "client_id": str(self.client_id) if self.client_id is not None else None,
            "level": self.level.value,
            "score": self.score,
            "reasons": self.reasons,
            "created_at": self.created_at.isoformat(),
        }

    def __str__(self) -> str:
        return (
            f"RiskAssessment | "
            f"id={self.assessment_id} | "
            f"transaction={self.transaction_id} | "
            f"level={self.level.value} | "
            f"score={self.score}"
        )
    

class RiskAnalyzer:
    def __init__(
        self,
        large_amount_threshold: Decimal | int | float | str = Decimal("1000000"),
        frequent_operations_limit: int = 5,
        frequent_operations_window_seconds: int = 60,
        medium_risk_threshold: int = 40,
        high_risk_threshold: int = 70,
        night_operations_are_high_risk: bool = True,
    ):
        self.large_amount_threshold = Decimal(str(large_amount_threshold))
        self.frequent_operations_limit = frequent_operations_limit
        self.frequent_operations_window = timedelta(
            seconds=frequent_operations_window_seconds
        )
        self.medium_risk_threshold = medium_risk_threshold
        self.high_risk_threshold = high_risk_threshold
        self.night_operations_are_high_risk = night_operations_are_high_risk

        self.assessments: list[RiskAssessment] = []
        self.operations_by_sender: dict[str, list[datetime]] = {}
        self.known_receivers_by_sender: dict[str, set[str]] = {}

        if self.large_amount_threshold <= 0:
            raise InvalidOperationError("Large amount threshold must be positive")

        if self.frequent_operations_limit <= 0:
            raise InvalidOperationError("Frequent operations limit must be positive")

        if self.medium_risk_threshold < 0:
            raise InvalidOperationError("Medium risk threshold cannot be negative")

        if self.high_risk_threshold <= self.medium_risk_threshold:
            raise InvalidOperationError(
                "High risk threshold must be greater than medium risk threshold"
            )

    def analyze(
        self,
        transaction: Transaction,
        bank,
        now: datetime | None = None,
    ) -> RiskAssessment:
        now = now or datetime.now()

        score = 0
        reasons = []

        sender_account = self._get_account_safely(
            bank=bank,
            account_id=transaction.sender_account_id,
        )

        client_id = getattr(sender_account, "owner_id", None)

        if transaction.amount >= self.large_amount_threshold:
            score += 40
            reasons.append("Large transaction amount")

        if self._is_frequent_operation(transaction, now):
            score += 30
            reasons.append("Too many operations in a short period")

        if self._is_new_receiver(transaction):
            score += 20
            reasons.append("Transfer to a new receiver")

        if self._is_night_operation(now):
            if self.night_operations_are_high_risk:
                score += 100
            else:
                score += 25

            reasons.append("Night operation")

        level = self._get_risk_level(score)

        assessment = RiskAssessment(
            transaction_id=transaction.transaction_id,
            client_id=client_id,
            level=level,
            score=score,
            reasons=reasons,
            created_at=now,
        )

        self.assessments.append(assessment)
        self._remember_operation(transaction, now)

        if level != RiskLevel.LOW and client_id is not None:
            self._mark_client_suspicious(
                bank=bank,
                client_id=client_id,
                assessment=assessment,
            )

        return assessment

    def _get_risk_level(self, score: int) -> RiskLevel:
        if score >= self.high_risk_threshold:
            return RiskLevel.HIGH

        if score >= self.medium_risk_threshold:
            return RiskLevel.MEDIUM

        return RiskLevel.LOW

    @staticmethod
    def _is_night_operation(now: datetime) -> bool:
        return 0 <= now.hour < 5

    def _is_frequent_operation(
        self,
        transaction: Transaction,
        now: datetime,
    ) -> bool:
        sender_id = transaction.sender_account_id

        if sender_id is None:
            return False

        timestamps = self.operations_by_sender.get(sender_id, [])

        recent_timestamps = [
            timestamp
            for timestamp in timestamps
            if now - timestamp <= self.frequent_operations_window
        ]

        return len(recent_timestamps) + 1 >= self.frequent_operations_limit

    def _is_new_receiver(self, transaction: Transaction) -> bool:
        if transaction.type not in {
            TransactionType.TRANSFER,
            TransactionType.EXTERNAL_TRANSFER,
        }:
            return False

        if transaction.sender_account_id is None:
            return False

        if transaction.receiver_account_id is None:
            return False

        known_receivers = self.known_receivers_by_sender.get(
            transaction.sender_account_id,
            set(),
        )

        return transaction.receiver_account_id not in known_receivers

    def _remember_operation(
        self,
        transaction: Transaction,
        now: datetime,
    ) -> None:
        sender_id = transaction.sender_account_id

        if sender_id is None:
            return

        self.operations_by_sender.setdefault(sender_id, []).append(now)

        self.operations_by_sender[sender_id] = [
            timestamp
            for timestamp in self.operations_by_sender[sender_id]
            if now - timestamp <= self.frequent_operations_window
        ]

        if transaction.receiver_account_id is not None:
            self.known_receivers_by_sender.setdefault(sender_id, set()).add(
                transaction.receiver_account_id
            )

    @staticmethod
    def _get_account_safely(
        bank,
        account_id: str | None,
    ):
        if account_id is None:
            return None

        if hasattr(bank, "accounts"):
            return bank.accounts.get(account_id)

        return None

    @staticmethod
    def _mark_client_suspicious(
        bank,
        client_id: str,
        assessment: RiskAssessment,
    ) -> None:
        if hasattr(bank, "mark_suspicious_action"):
            bank.mark_suspicious_action(
                client_id=client_id,
                reason=f"Risk level: {assessment.level.value}",
                data=assessment.to_dict(),
            )

    def get_suspicious_assessments(self) -> list[RiskAssessment]:
        return [
            assessment
            for assessment in self.assessments
            if assessment.level in {RiskLevel.MEDIUM, RiskLevel.HIGH}
        ]

    def get_client_risk_profile(self, client_id: str) -> dict:
        client_assessments = [
            assessment
            for assessment in self.assessments
            if assessment.client_id == client_id
        ]

        profile = {
            "client_id": client_id,
            "total_assessments": len(client_assessments),
            "low": 0,
            "medium": 0,
            "high": 0,
            "max_score": 0,
            "reasons": {},
        }

        for assessment in client_assessments:
            profile[assessment.level.value.lower()] += 1
            profile["max_score"] = max(profile["max_score"], assessment.score)

            for reason in assessment.reasons:
                profile["reasons"][reason] = profile["reasons"].get(reason, 0) + 1

        return profile

    def get_statistics(self) -> dict:
        statistics = {
            "total_assessments": len(self.assessments),
            "low": 0,
            "medium": 0,
            "high": 0,
            "blocked_candidates": 0,
            "reason_counts": {},
        }

        for assessment in self.assessments:
            statistics[assessment.level.value.lower()] += 1

            if assessment.level == RiskLevel.HIGH:
                statistics["blocked_candidates"] += 1

            for reason in assessment.reasons:
                statistics["reason_counts"][reason] = (
                    statistics["reason_counts"].get(reason, 0) + 1
                )

        return statistics

    def to_dict(self) -> list[dict]:
        return [
            assessment.to_dict()
            for assessment in self.assessments
        ]
