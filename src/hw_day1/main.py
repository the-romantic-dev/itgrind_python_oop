from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from enum import Enum, auto
import uuid

@dataclass
class PersonalData:
    first_name: str
    last_name: str
    middle_name: str | None
    brith_date: date

class AccountStatus(Enum):
    ACTIVE = 'Активный'
    FROZEN = 'Замороженный'
    CLOSED = 'Закрытый'


class AbstractAccount(ABC):
    def __init__(self, id: uuid.UUID, personal_data: PersonalData, status: AccountStatus, init_balance: float = 0.0):
        self.id = id
        self._balance = init_balance
        self.status = status
        self.personal_data = personal_data

    @abstractmethod
    def deposit(self, amount: float):
        pass
    
    @abstractmethod
    def withdraw(self, amount: float):
        pass

    @abstractmethod
    def get_account_info(self):
        pass


class AccountFrozenError(Exception):
    pass

class AccountClosedError(Exception):
    pass

class InvalidOperationError(Exception):
    pass

class InsufficientFundsError(Exception):
    pass

class BankAccount(AbstractAccount):
    def __init__(self, personal_data: PersonalData, currency: str, status: AccountStatus, init_balance = 0.0, id: uuid.UUID | None = None):
        if id is None:
            id = uuid.uuid4()
        super().__init__(id, personal_data, status, init_balance)
        self.currency = currency

    def _check_status(self):
        if self.status == AccountStatus.FROZEN:
            raise AccountFrozenError('Счет заморожен, взаимодействие невозможно')
        if self.status == AccountStatus.FROZEN:
            raise AccountClosedError('Счет закрыт, взаимодействие невозможно')

    def withdraw(self, amount: float):
        self._check_status()
        if amount <= 0:
            raise InvalidOperationError('Сумма выводимых средств должна быть больше 0')
        if amount <= self._balance:
            self._balance -= amount
        else:
            raise InsufficientFundsError('Недостаточно средств на счете')

    def deposit(self, amount):
        self._check_status()
        if amount <= 0:
            raise InvalidOperationError('Сумма вводимых средств должна быть больше 0')
        self._balance += amount


    def get_account_info(self):
        return {
            'personal_data': self.personal_data,
            'balance': self._balance,
            'currency': self.currency,
            'account_status': self.status
        }
    
    def __str__(self):
        fio = f"{self.personal_data.last_name} {self.personal_data.first_name} {self.personal_data.middle_name if self.personal_data.middle_name is not None else ''}"
        return f"""
Тип счета: {self.__class__.__name__}
ФИО клиента: {fio}
Дата рождения: {self.personal_data.brith_date.isoformat()}
ID счета: ****{str(self.id)[-4:]}
Статус: {self.status.value}
Баланс: {self._balance:.2f} {self.currency}
        """
    
