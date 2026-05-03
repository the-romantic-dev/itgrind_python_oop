from __future__ import annotations

from decimal import Decimal, InvalidOperation

from models.enums import Currency
from models.errors import InvalidOperationError


class CurrencyConverter:
    DEFAULT_RATES_TO_RUB = {
        Currency.RUB: Decimal("1"),
        Currency.USD: Decimal("90"),
        Currency.EUR: Decimal("100"),
        Currency.KZT: Decimal("0.2"),
        Currency.CNY: Decimal("12.5"),
    }

    def __init__(
        self,
        rates_to_rub: dict[Currency, Decimal | int | float | str] | None = None,
    ):
        self.rates_to_rub = self.DEFAULT_RATES_TO_RUB.copy()

        if rates_to_rub is not None:
            for currency, rate in rates_to_rub.items():
                self.set_rate(currency, rate)

    def convert(
        self,
        amount: Decimal | int | float | str,
        from_currency: Currency,
        to_currency: Currency,
    ) -> Decimal:
        amount = self._to_decimal(amount)

        if amount < 0:
            raise InvalidOperationError("Amount cannot be negative")

        from_currency = self._coerce_currency(from_currency)
        to_currency = self._coerce_currency(to_currency)

        if from_currency == to_currency:
            return amount

        amount_in_rub = amount * self.rates_to_rub[from_currency]
        converted = amount_in_rub / self.rates_to_rub[to_currency]

        return converted.quantize(Decimal("0.01"))

    def set_rate(
        self,
        currency: Currency,
        rate_to_rub: Decimal | int | float | str,
    ) -> None:
        currency = self._coerce_currency(currency)
        rate_to_rub = self._to_decimal(rate_to_rub)

        if rate_to_rub <= 0:
            raise InvalidOperationError("Currency rate must be positive")

        self.rates_to_rub[currency] = rate_to_rub

    def get_rate(self, currency: Currency) -> Decimal:
        currency = self._coerce_currency(currency)
        return self.rates_to_rub[currency]

    def get_rates(self) -> dict[str, str]:
        return {
            currency.value: str(rate)
            for currency, rate in self.rates_to_rub.items()
        }

    @staticmethod
    def _to_decimal(value: Decimal | int | float | str) -> Decimal:
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            raise InvalidOperationError(f"Invalid decimal value: {value}")

    @staticmethod
    def _coerce_currency(currency: Currency | str) -> Currency:
        if isinstance(currency, Currency):
            return currency

        if isinstance(currency, str):
            normalized = currency.upper().strip()

            for item in Currency:
                if item.value == normalized or item.name == normalized:
                    return item

        raise InvalidOperationError(f"Invalid currency: {currency}")