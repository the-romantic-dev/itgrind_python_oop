from datetime import date, datetime
import hashlib
import uuid

from models.enums import ClientStatus
from models.errors import AuthenticationError, ClientBlockedError, InvalidOperationError

class Client:
    MAX_FAILED_LOGIN_ATTEMPTS = 3

    def __init__(
        self,
        full_name: str,
        birth_date: date | str | None = None,
        age: int | None = None,
        contacts: dict | None = None,
        pin: str | None = None,
        status: ClientStatus = ClientStatus.ACTIVE,
        client_id: str | uuid.UUID | None = None,
    ):
        self.client_id = uuid.uuid4() if client_id is None else client_id

        self.full_name = full_name.strip()
        if not self.full_name:
            raise InvalidOperationError("Client name cannot be empty")

        self.birth_date = self._resolve_birth_date(birth_date, age)
        self._validate_age()
        self.contacts = contacts or {}

        self.status = status
        self.account_ids: list[str] = []

        self.failed_login_attempts = 0
        self.suspicious_actions: list[dict] = []

        self._pin_hash: str | None = None

        if pin is not None:
            self.set_pin(pin)

    @staticmethod
    def _resolve_birth_date(
        birth_date: date | str | None,
        age: int | None,
    ) -> date:
        if birth_date is not None:
            return (
                birth_date
                if isinstance(birth_date, date)
                else date.fromisoformat(birth_date)
            )

        if age is None:
            raise InvalidOperationError("Client birth date or age is required")

        if not isinstance(age, int) or age <= 0:
            raise InvalidOperationError("Client age must be a positive integer")

        today = datetime.now().date()
        return date(today.year - age, today.month, today.day)

    def _validate_age(self) -> int:
        today = datetime.now().date()
        age = today.year - self.birth_date.year

        if (today.month, today.day) < (self.birth_date.month, self.birth_date.day):
            age -= 1

        if age < 18:
            raise InvalidOperationError("Client must be older 18 years")

        return age

    @staticmethod
    def _hash_pin(pin: str) -> str:
        if not isinstance(pin, str) or not pin.strip():
            raise InvalidOperationError("PIN is empty")

        return hashlib.sha256(pin.encode("utf-8")).hexdigest()
    
    def set_pin(self, pin: str) -> None:
        self._pin_hash = self._hash_pin(pin)

    def check_pin(self, pin: str) -> bool:
        if self._pin_hash is None:
            raise AuthenticationError("Client hasn't PIN")

        return self._pin_hash == self._hash_pin(pin)
    
    def register_successful_login(self) -> None:
        self.failed_login_attempts = 0

    def register_failed_login(self) -> None:
        self.failed_login_attempts += 1

        if self.failed_login_attempts >= self.MAX_FAILED_LOGIN_ATTEMPTS:
            self.block()

    def block(self) -> None:
        self.status = ClientStatus.BLOCKED
    
    def unblock(self) -> None:
        self.status = ClientStatus.ACTIVE
        self.failed_login_attempts = 0

    def ensure_active(self) -> None:
        if self.status == ClientStatus.BLOCKED:
            raise ClientBlockedError("Client blocked")
        
    def add_account(self, account_id: str) -> None:
        if account_id not in self.account_ids:
            self.account_ids.append(account_id)
    
    def remove_account(self, account_id: str) -> None:
        if account_id in self.account_ids:
            self.account_ids.remove(account_id)
    
    def mark_suspicious_action(
        self,
        reason: str,
        data: dict | None = None,
    ) -> None:
        self.suspicious_actions.append(
            {
                "reason": reason,
                "data": data or {},
            }
        )

    def get_client_info(self) -> dict:
        return {
            "client_id": str(self.client_id),
            "full_name": self.full_name,
            "birth_date": self.birth_date.isoformat(),
            "status": self.status.value,
            "contacts": self.contacts,
            "account_ids": [str(account_id) for account_id in self.account_ids],
            "failed_login_attempts": self.failed_login_attempts,
            "suspicious_actions_count": len(self.suspicious_actions),
        }

    def __str__(self) -> str:
        return (
            f"Client\n"
            f"ID: {self.client_id}\n"
            f"Name: {self.full_name}\n"
            f"Birth date: {self.birth_date.isoformat()}\n"
            f"Status: {self.status.value}\n"
            f"Accounts: {len(self.account_ids)}"
        )
