import contextvars
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator, Generator, Generic, TypeVar

from pydantic_filters import BasePagination, BaseSort
from pydantic_filters.drivers.sqlalchemy import append_to_statement
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import delete, insert, select, update
from sqlmodel.ext.asyncio.session import AsyncSession

from .exceptions import AlreadyExistsError, HaveNoSessionError
from .settings import DatabaseSettings
from .tables import BaseTable


DTOType = TypeVar("DTOType")
FilterType = TypeVar("FilterType")


class BaseRepository(Generic[DTOType, FilterType]):
    def __init__(self, settings: DatabaseSettings):
        self._settings = settings

        engine_parameters = {
            "url": str(self._settings.dsn),
            "pool_recycle": self._settings.pool_recycle,
        }
        if not str(self._settings.dsn).startswith("sqlite"):
            engine_parameters["pool_timeout"] = self._settings.pool_timeout
            engine_parameters["pool_size"] = self._settings.pool_size

        self._engine = create_async_engine(**engine_parameters)
        self._session_context = contextvars.ContextVar("session_context")

    @property
    def session(self) -> AsyncSession:
        session = self._session_context.get(None)
        if session is None:
            raise HaveNoSessionError()

        return session

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[None, None]:
        session_args = {"bind": self._engine, "expire_on_commit": False}
        async with AsyncSession(**session_args) as session:
            with self._set_session_to_session_context(session=session):
                async with session.begin():
                    yield

    @contextmanager
    def _set_session_to_session_context(self, session: AsyncSession) -> Generator[None, None, None]:
        token = self._session_context.set(session)
        yield
        self._session_context.reset(token)

    def get_db_table(self) -> type[BaseTable]:
        raise NotImplementedError

    async def get_items_count(
            self,
            filter_: FilterType | None = None,
    ) -> int:
        table = self.get_db_table()
        statement = select(func.count())
        statement = append_to_statement(
            statement=statement,
            model=table,
            filter_=filter_,
        )

        result = await self.session.exec(statement)
        items_count = result.first()

        return items_count

    async def get_items(
        self,
        filter_: FilterType | None = None,
        pagination: BasePagination | None = None,
        sort: BaseSort | None = None,
        options: list | None = None,
) -> AsyncGenerator[DTOType]:
        table = self.get_db_table()
        statement = select(table)
        statement = append_to_statement(
            statement=statement,
            model=table,
            filter_=filter_,
            pagination=pagination,
            sort=sort,
        )
        if options:
            statement = statement.options(*options)

        result = await self.session.exec(statement)
        db_items = result.all()

        for db_item in db_items:
            yield db_item.to_item()

    async def create_item(self, item: DTOType) -> DTOType:
        table = self.get_db_table()
        values = table.from_item(item=item).to_values()
        statement = insert(table).values(values).returning(table)

        try:
            result = await self.session.exec(statement)
        except IntegrityError:
            raise AlreadyExistsError(model=table, values=values)
        db_item = result.first()[0]

        return db_item.to_item()

    async def update_items(
            self,
            filter_: FilterType | None = None,
            **values,
    ) -> AsyncGenerator[DTOType]:
        table = self.get_db_table()
        statement = update(table)
        statement = append_to_statement(
            statement=statement,
            model=table,
            filter_=filter_,
        )
        statement = statement.values(**values).returning(table)

        result = await self.session.exec(statement)
        db_items = result.all()

        for db_item, *_ in db_items:
            yield db_item.to_item()

    async def delete_items(
            self,
            filter_: FilterType | None = None,
            pagination: BasePagination | None = None,
            sort: BaseSort | None = None,
    ):
        table = self.get_db_table()
        statement = delete(table)
        statement = append_to_statement(
            statement=statement,
            model=table,
            filter_=filter_,
            pagination=pagination,
            sort=sort,
        )

        await self.session.exec(statement)
