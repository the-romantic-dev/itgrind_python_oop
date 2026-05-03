# Банковская система на Python ООП

Учебный проект по объектно-ориентированному программированию: модель банковских
счетов, клиентов, транзакций, аудита, риск-анализа, отчетности и визуализации.

## Что реализовано

Проект собирает задания из `day1.txt` - `day7.txt` в одну банковскую систему:

- базовая модель счета `BankAccount` и абстрактный `AbstractAccount`;
- типы счетов: `SavingsAccount`, `PremiumAccount`, `InvestmentAccount`;
- клиентская модель `Client` и управляющий сервис `Bank`;
- очередь и обработчик транзакций: `TransactionQueue`, `TransactionProcessor`;
- комиссии, конвертация валют и внешние переводы;
- блокировка операций по статусам счетов, ночным ограничениям и риск-анализу;
- аудит событий через `AuditLog`;
- риск-анализ через `RiskAnalyzer`;
- отчеты JSON/CSV/text и графики через `ReportBuilder`;
- комплексное демо в `src/demo.py`;
- тесты актуальной архитектуры в `tests/test_main.py`.

## Структура

```text
src/
  demo.py                         # комплексная демонстрация проекта
  main.py                         # совместимый фасад старого учебного API
  models/
    accounts.py                   # счета
    client.py                     # клиенты
    enums.py                      # enum-статусы и типы
    errors.py                     # пользовательские исключения
    transaction.py                # модель транзакции
  services/
    audit_log.py                  # аудит
    bank.py                       # банк и операции с клиентами/счетами
    currency_converter.py         # конвертация валют
    report_builder.py             # отчеты и графики
    risk_analyzer.py              # риск-анализ
    transaction_processor.py      # обработка транзакций
    transaction_queue.py          # очередь транзакций
tests/
  test_main.py                    # тесты текущей реализации
output/
  logs/                           # audit.json после запуска демо
  reports/                        # JSON/CSV/text отчеты
  charts/                         # PNG-графики
```

## Установка

Команды ниже рассчитаны на Windows PowerShell из корня проекта.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Если виртуальное окружение уже создано, достаточно установить зависимости:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Запуск демо

```powershell
.\.venv\Scripts\python.exe src\demo.py
```

Демо создает:

- 6 клиентов;
- 12 счетов разных типов;
- 41 транзакцию;
- успешные, ошибочные, отмененные, отложенные и подозрительные операции;
- аудит, отчеты и графики.

После успешного запуска в конце будет секция `Demo completed`.

## Запуск тестов

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Ожидаемый результат:

```text
7 passed
```

## Результаты демо

После запуска `src/demo.py` файлы появляются в `output/`:

```text
output/logs/audit.json
output/reports/bank_report.json
output/reports/risk_report.json
output/reports/client_report.json
output/reports/bank_report.csv
output/reports/bank_report.txt
output/charts/transaction_statuses.png
output/charts/clients_balance.png
output/charts/balance_movement.png
```

## Зависимости

Список зависимостей находится в `requirements.txt`:

- `pytest` - запуск тестов;
- `matplotlib` - построение графиков в отчетах.

## Примечания

- Основной сценарий проекта находится в `src/demo.py`.
- Файл `src/main.py` оставлен как совместимый фасад для старого варианта учебных тестов.
- Актуальные тесты используют реальные модули из `src/models` и `src/services`.
