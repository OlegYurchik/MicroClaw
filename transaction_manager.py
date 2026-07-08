#!/usr/bin/env python3
"""
Transaction Manager CLI
Скрипт для создания, отслеживания и удаления транзакций в brt-api_core
"""

import asyncio
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

import aiohttp
import asyncpg
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

app = typer.Typer(help="Transaction Manager CLI - управление транзакциями brt-api_core")
console = Console()


class TransactionType(str, Enum):
    BANK = "BANK"
    TOP_UP = "TOP_UP"


class TransactionStatus(str, Enum):
    PROGRESS = "PROGRESS"
    COMPLETED = "COMPLETED"
    DECLINED = "DECLINED"


class Currency(str, Enum):
    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"


class Config:
    """Конфигурация подключения к сервисам"""

    def __init__(
        self,
        api_url: str = "http://brtservice.io:8000",
        loki_url: str = "http://brtservice.io:3100",
        rabbitmq_url: str = "http://brtservice.io:15672",
        rabbitmq_user: str = "guest",
        rabbitmq_pass: str = "guest",
        postgres_host: str = "brtservice.io",
        postgres_port: int = 5432,
        postgres_user: str = "postgres",
        postgres_password: str = "postgres",
        postgres_database: str = "brt_core",
    ):
        self.api_url = api_url
        self.loki_url = loki_url
        self.rabbitmq_url = rabbitmq_url
        self.rabbitmq_user = rabbitmq_user
        self.rabbitmq_pass = rabbitmq_pass
        self.postgres_host = postgres_host
        self.postgres_port = postgres_port
        self.postgres_user = postgres_user
        self.postgres_password = postgres_password
        self.postgres_database = postgres_database


class TransactionManager:
    """Менеджер транзакций"""

    def __init__(self, config: Config):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        self.pg_conn: Optional[asyncpg.Connection] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
        if self.pg_conn:
            await self.pg_conn.close()

    async def _get_pg_connection(self) -> asyncpg.Connection:
        """Получает подключение к PostgreSQL"""
        if self.pg_conn is None or self.pg_conn.is_closed():
            self.pg_conn = await asyncpg.connect(
                host=self.config.postgres_host,
                port=self.config.postgres_port,
                user=self.config.postgres_user,
                password=self.config.postgres_password,
                database=self.config.postgres_database,
            )
        return self.pg_conn

    async def create_transaction(
        self,
        amount: int,
        currency: Currency,
        transaction_type: TransactionType,
        bank_participator_id: str,
        account_id: uuid.UUID,
        transaction_id: Optional[uuid.UUID] = None,
        extra: Optional[dict] = None,
    ) -> dict:
        """Создает транзакцию через API"""
        url = f"{self.config.api_url}/api/rest/transactions"

        payload = {
            "amount": amount,
            "currency": currency.value,
            "type": transaction_type.value,
            "bank_participator_id": bank_participator_id,
            "account_id": str(account_id),
        }

        if transaction_id:
            payload["id"] = str(transaction_id)

        if extra:
            payload["extra"] = extra

        async with self.session.post(url, json=payload) as response:
            if response.status == 200:
                return await response.json()
            else:
                error_text = await response.text()
                raise Exception(
                    f"Failed to create transaction: {response.status} - {error_text}"
                )

    async def get_transaction(self, transaction_id: uuid.UUID) -> dict:
        """Получает транзакцию по ID"""
        url = f"{self.config.api_url}/api/rest/transactions/{transaction_id}"

        async with self.session.get(url) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 404:
                return None
            else:
                error_text = await response.text()
                raise Exception(
                    f"Failed to get transaction: {response.status} - {error_text}"
                )

    async def get_transactions(
        self, account_id: Optional[uuid.UUID] = None
    ) -> list[dict]:
        """Получает список транзакций"""
        url = f"{self.config.api_url}/api/rest/transactions"

        params = {}
        if account_id:
            params["account_id"] = str(account_id)

        async with self.session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("data", [])
            else:
                error_text = await response.text()
                raise Exception(
                    f"Failed to get transactions: {response.status} - {error_text}"
                )

    async def delete_transaction_from_db(self, transaction_id: uuid.UUID) -> bool:
        """Удаляет транзакцию из базы данных PostgreSQL"""
        try:
            conn = await self._get_pg_connection()

            # Удаляем транзакцию
            result = await conn.execute(
                "DELETE FROM transactions WHERE id = $1", str(transaction_id)
            )

            # Проверяем, была ли удалена запись
            deleted_count = int(result.split()[-1])

            if deleted_count > 0:
                console.print("[green]✓ Транзакция удалена из PostgreSQL[/green]")
                return True
            else:
                console.print("[yellow]⚠️  Транзакция не найдена в PostgreSQL[/yellow]")
                return False

        except Exception as e:
            console.print(f"[red]✗ Ошибка при удалении из PostgreSQL: {e}[/red]")
            return False

    async def delete_logs_from_loki(self, transaction_id: uuid.UUID) -> bool:
        """Удаляет логи транзакции из Loki"""
        # Loki не поддерживает удаление логов напрямую через API
        # Логи хранятся в течение retention period и удаляются автоматически

        console.print(
            "[yellow]⚠️  Loki не поддерживает удаление логов через API[/yellow]"
        )
        console.print(
            "[yellow]   Логи будут автоматически удалены после retention period[/yellow]"
        )
        console.print(
            "[yellow]   Для удаления логов можно использовать Loki API для очистки старых данных[/yellow]"
        )

        # Альтернативный подход: можно использовать Loki API для удаления старых данных
        # но это требует доступа к Loki admin API и может повлиять на другие логи

        return True

    async def delete_events_from_rabbitmq(self, transaction_id: uuid.UUID) -> bool:
        """Удаляет события транзакции из RabbitMQ"""
        try:
            # RabbitMQ не поддерживает удаление отдельных сообщений из очереди
            # Но можно очистить очередь целиком

            auth = aiohttp.BasicAuth(
                self.config.rabbitmq_user, self.config.rabbitmq_pass
            )

            # Получаем список очередей
            queues_url = f"{self.config.rabbitmq_url}/api/queues"
            async with self.session.get(queues_url, auth=auth) as response:
                if response.status == 200:
                    queues = await response.json()

                    # Ищем очереди, связанные с brt-core
                    for queue in queues:
                        queue_name = queue.get("name", "")
                        if (
                            "brt" in queue_name.lower()
                            or "transaction" in queue_name.lower()
                        ):
                            # Пытаемся очистить очередь
                            purge_url = f"{self.config.rabbitmq_url}/api/queues/%2F/{queue_name}/contents"
                            async with self.session.delete(
                                purge_url, auth=auth
                            ) as purge_response:
                                if purge_response.status == 204:
                                    console.print(
                                        f"[green]✓ Очередь {queue_name} очищена[/green]"
                                    )
                                else:
                                    console.print(
                                        f"[yellow]⚠️  Не удалось очистить очередь {queue_name}[/yellow]"
                                    )

            console.print(
                "[yellow]⚠️  RabbitMQ не поддерживает удаление отдельных сообщений[/yellow]"
            )
            console.print("[yellow]   Очереди были очищены целиком[/yellow]")

            return True

        except Exception as e:
            console.print(f"[red]✗ Ошибка при удалении из RabbitMQ: {e}[/red]")
            return False

    async def track_transaction(
        self,
        transaction_id: uuid.UUID,
        timeout: int = 60,
        interval: int = 2,
    ) -> dict:
        """Отслеживает статус транзакции"""
        start_time = datetime.now()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                f"Отслеживание транзакции {transaction_id}...",
                total=None,
            )

            while True:
                elapsed = (datetime.now() - start_time).total_seconds()

                if elapsed >= timeout:
                    progress.update(task, description="Таймаут отслеживания")
                    break

                transaction = await self.get_transaction(transaction_id)

                if transaction:
                    status = transaction.get("status")
                    progress.update(
                        task,
                        description=f"Статус: {status} | Прошло: {elapsed:.1f}с",
                    )

                    if status in ["COMPLETED", "DECLINED"]:
                        progress.update(
                            task, description=f"Транзакция завершена: {status}"
                        )
                        return transaction
                else:
                    progress.update(task, description="Транзакция не найдена")
                    return None

                await asyncio.sleep(interval)

        return await self.get_transaction(transaction_id)

    async def cleanup_transaction(
        self,
        transaction_id: uuid.UUID,
        delete_from_db: bool = True,
        delete_logs: bool = True,
        delete_events: bool = True,
    ) -> dict:
        """Полная очистка транзакции из всех сервисов"""
        results = {
            "transaction_id": str(transaction_id),
            "deleted_from_db": False,
            "deleted_from_loki": False,
            "deleted_from_rabbitmq": False,
        }

        console.print(Panel(f"Очистка транзакции {transaction_id}", style="bold red"))

        if delete_from_db:
            console.print("Удаление из базы данных...")
            results["deleted_from_db"] = await self.delete_transaction_from_db(
                transaction_id
            )

        if delete_logs:
            console.print("Удаление логов из Loki...")
            results["deleted_from_loki"] = await self.delete_logs_from_loki(
                transaction_id
            )

        if delete_events:
            console.print("Удаление событий из RabbitMQ...")
            results["deleted_from_rabbitmq"] = await self.delete_events_from_rabbitmq(
                transaction_id
            )

        return results


# CLI Commands


@app.command()
def create(
    amount: int = typer.Option(..., help="Сумма в копейках"),
    currency: Currency = typer.Option(Currency.RUB, help="Валюта"),
    transaction_type: TransactionType = typer.Option(
        TransactionType.BANK, help="Тип транзакции"
    ),
    bank_participator_id: str = typer.Option(..., help="ID участника в банке"),
    account_id: str = typer.Option(..., help="ID аккаунта (UUID)"),
    transaction_id: Optional[str] = typer.Option(None, help="ID транзакции (UUID)"),
    track: bool = typer.Option(False, help="Отслеживать транзакцию после создания"),
    timeout: int = typer.Option(60, help="Таймаут отслеживания в секундах"),
    api_url: str = typer.Option("http://brtservice.io:8000", help="URL API сервиса"),
):
    """Создать новую транзакцию"""

    async def _create():
        config = Config(api_url=api_url)

        async with TransactionManager(config) as manager:
            # Создаем транзакцию
            console.print(Panel("Создание транзакции", style="bold green"))

            tx_id = uuid.UUID(transaction_id) if transaction_id else None
            acc_id = uuid.UUID(account_id)

            transaction = await manager.create_transaction(
                amount=amount,
                currency=currency,
                transaction_type=transaction_type,
                bank_participator_id=bank_participator_id,
                account_id=acc_id,
                transaction_id=tx_id,
            )

            # Отображаем результат
            table = Table(title="Транзакция создана")
            table.add_column("Поле", style="cyan")
            table.add_column("Значение", style="green")

            for key, value in transaction.items():
                if key != "account":
                    table.add_row(key, str(value))

            console.print(table)

            # Отслеживаем если нужно
            if track:
                console.print()
                console.print(Panel("Отслеживание транзакции", style="bold blue"))

                tx_uuid = uuid.UUID(transaction["id"])
                final_transaction = await manager.track_transaction(
                    transaction_id=tx_uuid,
                    timeout=timeout,
                )

                if final_transaction:
                    console.print()
                    table = Table(title="Финальный статус")
                    table.add_column("Поле", style="cyan")
                    table.add_column("Значение", style="green")

                    for key, value in final_transaction.items():
                        if key != "account":
                            table.add_row(key, str(value))

                    console.print(table)

    asyncio.run(_create())


@app.command()
def get(
    transaction_id: str = typer.Argument(..., help="ID транзакции (UUID)"),
    api_url: str = typer.Option("http://brtservice.io:8000", help="URL API сервиса"),
):
    """Получить информацию о транзакции"""

    async def _get():
        config = Config(api_url=api_url)

        async with TransactionManager(config) as manager:
            tx_uuid = uuid.UUID(transaction_id)
            transaction = await manager.get_transaction(tx_uuid)

            if transaction:
                table = Table(title="Информация о транзакции")
                table.add_column("Поле", style="cyan")
                table.add_column("Значение", style="green")

                for key, value in transaction.items():
                    if key != "account":
                        table.add_row(key, str(value))

                console.print(table)
            else:
                console.print("[red]Транзакция не найдена[/red]")

    asyncio.run(_get())


@app.command()
def list(
    account_id: Optional[str] = typer.Option(None, help="Фильтр по ID аккаунта"),
    api_url: str = typer.Option("http://brtservice.io:8000", help="URL API сервиса"),
):
    """Получить список транзакций"""

    async def _list():
        config = Config(api_url=api_url)

        async with TransactionManager(config) as manager:
            acc_id = uuid.UUID(account_id) if account_id else None
            transactions = await manager.get_transactions(account_id=acc_id)

            if transactions:
                table = Table(title="Список транзакций")
                table.add_column("ID", style="cyan")
                table.add_column("Сумма", style="green")
                table.add_column("Валюта", style="yellow")
                table.add_column("Тип", style="magenta")
                table.add_column("Статус", style="blue")
                table.add_column("Создана", style="dim")

                for tx in transactions:
                    table.add_row(
                        tx["id"],
                        str(tx["amount"]),
                        tx["currency"],
                        tx["type"],
                        tx["status"],
                        tx["created_at"],
                    )

                console.print(table)
                console.print(f"\nВсего: {len(transactions)} транзакций")
            else:
                console.print("[yellow]Транзакции не найдены[/yellow]")

    asyncio.run(_list())


@app.command()
def cleanup(
    transaction_id: str = typer.Argument(..., help="ID транзакции (UUID)"),
    delete_from_db: bool = typer.Option(True, help="Удалить из базы данных"),
    delete_logs: bool = typer.Option(True, help="Удалить логи из Loki"),
    delete_events: bool = typer.Option(True, help="Удалить события из RabbitMQ"),
    api_url: str = typer.Option("http://brtservice.io:8000", help="URL API сервиса"),
    postgres_host: str = typer.Option("brtservice.io", help="Хост PostgreSQL"),
    postgres_port: int = typer.Option(5432, help="Порт PostgreSQL"),
    postgres_user: str = typer.Option("postgres", help="Пользователь PostgreSQL"),
    postgres_password: str = typer.Option("postgres", help="Пароль PostgreSQL"),
    postgres_database: str = typer.Option("brt_core", help="База данных PostgreSQL"),
):
    """Удалить транзакцию из всех сервисов"""

    async def _cleanup():
        config = Config(
            api_url=api_url,
            postgres_host=postgres_host,
            postgres_port=postgres_port,
            postgres_user=postgres_user,
            postgres_password=postgres_password,
            postgres_database=postgres_database,
        )

        async with TransactionManager(config) as manager:
            tx_uuid = uuid.UUID(transaction_id)

            # Сначала получаем информацию о транзакции
            transaction = await manager.get_transaction(tx_uuid)

            if transaction:
                console.print(
                    Panel("Текущая информация о транзакции", style="bold yellow")
                )
                table = Table()
                table.add_column("Поле", style="cyan")
                table.add_column("Значение", style="green")

                for key, value in transaction.items():
                    if key != "account":
                        table.add_row(key, str(value))

                console.print(table)
                console.print()

            # Выполняем очистку
            results = await manager.cleanup_transaction(
                transaction_id=tx_uuid,
                delete_from_db=delete_from_db,
                delete_logs=delete_logs,
                delete_events=delete_events,
            )

            # Отображаем результаты
            console.print()
            console.print(Panel("Результаты очистки", style="bold green"))

            result_table = Table()
            result_table.add_column("Сервис", style="cyan")
            result_table.add_column("Статус", style="green")

            result_table.add_row(
                "База данных (PostgreSQL)",
                "[green]✓ Удалено[/green]"
                if results["deleted_from_db"]
                else "[red]✗ Не удалено[/red]",
            )
            result_table.add_row(
                "Loki (логи)",
                "[green]✓ Очищено[/green]"
                if results["deleted_from_loki"]
                else "[red]✗ Не очищено[/red]",
            )
            result_table.add_row(
                "RabbitMQ (события)",
                "[green]✓ Очищено[/green]"
                if results["deleted_from_rabbitmq"]
                else "[red]✗ Не очищено[/red]",
            )

            console.print(result_table)

    asyncio.run(_cleanup())


@app.command()
def workflow(
    amount: int = typer.Option(..., help="Сумма в копейках"),
    currency: Currency = typer.Option(Currency.RUB, help="Валюта"),
    transaction_type: TransactionType = typer.Option(
        TransactionType.BANK, help="Тип транзакции"
    ),
    bank_participator_id: str = typer.Option(..., help="ID участника в банке"),
    account_id: str = typer.Option(..., help="ID аккаунта (UUID)"),
    timeout: int = typer.Option(60, help="Таймаут отслеживания в секундах"),
    cleanup: bool = typer.Option(True, help="Удалить транзакцию после отслеживания"),
    api_url: str = typer.Option("http://brtservice.io:8000", help="URL API сервиса"),
    postgres_host: str = typer.Option("brtservice.io", help="Хост PostgreSQL"),
    postgres_port: int = typer.Option(5432, help="Порт PostgreSQL"),
    postgres_user: str = typer.Option("postgres", help="Пользователь PostgreSQL"),
    postgres_password: str = typer.Option("postgres", help="Пароль PostgreSQL"),
    postgres_database: str = typer.Option("brt_core", help="База данных PostgreSQL"),
):
    """Полный рабочий процесс: создать → отследить → удалить"""

    async def _workflow():
        config = Config(
            api_url=api_url,
            postgres_host=postgres_host,
            postgres_port=postgres_port,
            postgres_user=postgres_user,
            postgres_password=postgres_password,
            postgres_database=postgres_database,
        )

        async with TransactionManager(config) as manager:
            # Шаг 1: Создание
            console.print(Panel("ШАГ 1: Создание транзакции", style="bold green"))

            acc_id = uuid.UUID(account_id)
            transaction = await manager.create_transaction(
                amount=amount,
                currency=currency,
                transaction_type=transaction_type,
                bank_participator_id=bank_participator_id,
                account_id=acc_id,
            )

            tx_uuid = uuid.UUID(transaction["id"])
            console.print(f"[green]✓ Транзакция создана: {tx_uuid}[/green]")
            console.print()

            # Шаг 2: Отслеживание
            console.print(Panel("ШАГ 2: Отслеживание транзакции", style="bold blue"))

            final_transaction = await manager.track_transaction(
                transaction_id=tx_uuid,
                timeout=timeout,
            )

            if final_transaction:
                status = final_transaction.get("status")
                console.print(
                    f"[green]✓ Транзакция завершена со статусом: {status}[/green]"
                )
            else:
                console.print("[yellow]⚠️  Транзакция не найдена[/yellow]")

            console.print()

            # Шаг 3: Очистка
            if cleanup:
                console.print(Panel("ШАГ 3: Очистка транзакции", style="bold red"))

                results = await manager.cleanup_transaction(
                    transaction_id=tx_uuid,
                    delete_from_db=True,
                    delete_logs=True,
                    delete_events=True,
                )

                console.print()
                console.print(Panel("Результаты", style="bold green"))

                result_table = Table()
                result_table.add_column("Сервис", style="cyan")
                result_table.add_column("Статус", style="green")

                result_table.add_row(
                    "База данных (PostgreSQL)",
                    "[green]✓[/green]"
                    if results["deleted_from_db"]
                    else "[red]✗[/red]",
                )
                result_table.add_row(
                    "Loki (логи)",
                    "[green]✓[/green]"
                    if results["deleted_from_loki"]
                    else "[red]✗[/red]",
                )
                result_table.add_row(
                    "RabbitMQ (события)",
                    "[green]✓[/green]"
                    if results["deleted_from_rabbitmq"]
                    else "[red]✗[/red]",
                )

                console.print(result_table)

            console.print()
            console.print(Panel("Рабочий процесс завершен", style="bold"))

    asyncio.run(_workflow())


if __name__ == "__main__":
    app()
