from datetime import timedelta
import uuid

from pydantic_filters import BaseSort, SortByOrder
from pydantic_filters.pagination import OffsetPagination
import pytest

from microclaw.dto import UserRoleEnum
from microclaw.users_storages.dto import (
    CronCreate,
    CronUpdate,
    TokenCreate,
    TokenUpdate,
    UserChannelCreate,
    UserChannelUpdate,
    UserCreate,
    UserUpdate,
)
from microclaw.users_storages.exceptions import AlreadyExistsError
from microclaw.users_storages.filters import (
    CronFilter,
    TokenFilter,
    UserChannelFilter,
    UserFilter,
)
from microclaw.users_storages.interfaces import UsersStorageInterface
from microclaw.utils import utcnow


async def assert_user_crud(storage: UsersStorageInterface) -> None:
    user1 = await storage.create_user(data=UserCreate(role=UserRoleEnum.USER))
    user2 = await storage.create_user(data=UserCreate(role=UserRoleEnum.ADMIN))

    fetched = await storage.get_user(filter_=UserFilter(id={user1.id}))
    assert fetched is not None
    assert fetched.id == user1.id
    assert fetched.role == UserRoleEnum.USER

    assert await storage.get_user(filter_=UserFilter(id={uuid.uuid4()})) is None

    users = [u async for u in storage.get_users()]
    assert len(users) == 2

    admins = [
        u
        async for u in storage.get_users(filter_=UserFilter(role={UserRoleEnum.ADMIN}))
    ]
    assert len(admins) == 1
    assert admins[0].id == user2.id

    updated = None
    async for u in storage.update_users(
        filter_=UserFilter(id={user1.id}),
        data=UserUpdate(agent={"model": "x"}),
    ):
        updated = u
    assert updated is not None
    assert updated.agent == {"model": "x"}

    not_found = None
    async for u in storage.update_users(
        filter_=UserFilter(id={uuid.uuid4()}),
        data=UserUpdate(agent={"model": "y"}),
    ):
        not_found = u
    assert not_found is None

    async for _ in storage.update_users(
        filter_=UserFilter(role={UserRoleEnum.USER}),
        data=UserUpdate(agent={"bulk": True}),
    ):
        pass
    users = [
        u async for u in storage.get_users(filter_=UserFilter(role={UserRoleEnum.USER}))
    ]
    assert len(users) == 1
    assert users[0].agent == {"bulk": True}

    await storage.delete_user(filter_=UserFilter(id={user2.id}))
    assert await storage.get_user(filter_=UserFilter(id={user2.id})) is None

    await storage.delete_user(filter_=UserFilter(id={uuid.uuid4()}))

    with pytest.raises(AlreadyExistsError):
        await storage.create_user(data=UserCreate(id=user1.id))


async def assert_user_channel_crud(storage: UsersStorageInterface) -> None:
    user = await storage.create_user(data=UserCreate())

    session_id = uuid.uuid4()
    channel = await storage.create_user_channel(
        data=UserChannelCreate(
            user_id=user.id,
            channel_key="tg",
            channel_internal_id="123",
            actual_session_id=session_id,
        )
    )
    assert channel.user_id == user.id
    assert channel.channel_key == "tg"
    assert channel.channel_internal_id == "123"

    channels = [c async for c in storage.get_user_channels()]
    assert len(channels) == 1

    channels = [
        c
        async for c in storage.get_user_channels(
            filter_=UserChannelFilter(user_id={user.id})
        )
    ]
    assert len(channels) == 1

    new_session = uuid.uuid4()
    updated_channels = [
        c
        async for c in storage.update_user_channels(
            filter_=UserChannelFilter(channel_key={"tg"}),
            data=UserChannelUpdate(actual_session_id=new_session),
        )
    ]
    assert len(updated_channels) == 1
    assert updated_channels[0].actual_session_id == new_session

    channels = [
        c
        async for c in storage.get_user_channels(
            filter_=UserChannelFilter(actual_session_id={new_session})
        )
    ]
    assert len(channels) == 1

    renamed = [
        c
        async for c in storage.update_user_channels(
            filter_=UserChannelFilter(channel_key={"tg"}),
            data=UserChannelUpdate(channel_key="vk"),
        )
    ]
    assert len(renamed) == 1
    assert renamed[0].channel_key == "vk"

    channels = [
        c
        async for c in storage.get_user_channels(
            filter_=UserChannelFilter(channel_key={"vk"})
        )
    ]
    assert len(channels) == 1

    await storage.delete_user_channels(filter_=UserChannelFilter(user_id={user.id}))
    channels = [c async for c in storage.get_user_channels()]
    assert len(channels) == 0


async def assert_token_crud(storage: UsersStorageInterface) -> None:
    user = await storage.create_user(data=UserCreate())

    future = utcnow() + timedelta(days=90)
    past = utcnow() - timedelta(days=1)

    token1 = await storage.create_token(
        data=TokenCreate(user_id=user.id, expires_at=future)
    )
    assert token1.token
    assert token1.user_id == user.id
    assert token1.is_valid()

    token2 = await storage.create_token(
        data=TokenCreate(user_id=user.id, token="abc123", expires_at=past)
    )
    assert token2.token == "abc123"

    fetched = await storage.get_token(filter_=TokenFilter(token={"abc123"}))
    assert fetched is not None
    assert fetched.token == "abc123"

    tokens = [
        t async for t in storage.get_tokens(filter_=TokenFilter(user_id={user.id}))
    ]
    assert len(tokens) == 2

    tokens = [
        t async for t in storage.get_tokens(filter_=TokenFilter(token={"abc123"}))
    ]
    assert len(tokens) == 1

    tokens = [
        t
        async for t in storage.get_tokens(filter_=TokenFilter(expires_at__gt=utcnow()))
    ]
    assert len(tokens) == 1
    assert tokens[0].token == token1.token

    tokens = [
        t
        async for t in storage.get_tokens(filter_=TokenFilter(expires_at__lt=utcnow()))
    ]
    assert len(tokens) == 1
    assert tokens[0].token == "abc123"

    new_expiry = utcnow() + timedelta(days=1)
    updated = None
    async for t in storage.update_tokens(
        filter_=TokenFilter(token={"abc123"}),
        data=TokenUpdate(expires_at=new_expiry),
    ):
        updated = t
    assert updated is not None
    assert updated.expires_at == new_expiry

    await storage.delete_token(filter_=TokenFilter(token={"abc123"}))
    assert await storage.get_token(filter_=TokenFilter(token={"abc123"})) is None

    await storage.delete_tokens(filter_=TokenFilter(user_id={user.id}))
    tokens = [t async for t in storage.get_tokens()]
    assert len(tokens) == 0


async def assert_cron_crud(storage: UsersStorageInterface) -> None:
    user = await storage.create_user(data=UserCreate())

    cron1 = await storage.create_cron(
        data=CronCreate(user_id=user.id, path="a.b", cron="*/5 * * * *")
    )
    await storage.create_cron(
        data=CronCreate(user_id=user.id, path="c.d", cron="0 0 * * *", enabled=False)
    )

    crons = [c async for c in storage.get_crons()]
    assert len(crons) == 2

    fetched = await storage.get_cron(filter_=CronFilter(id={cron1.id}))
    assert fetched is not None
    assert fetched.id == cron1.id

    crons = [c async for c in storage.get_crons(filter_=CronFilter(user_id={user.id}))]
    assert len(crons) == 2

    crons = [c async for c in storage.get_crons(filter_=CronFilter(id={cron1.id}))]
    assert len(crons) == 1

    crons = [c async for c in storage.get_crons(filter_=CronFilter(enabled=True))]
    assert len(crons) == 1
    assert crons[0].id == cron1.id

    updated = None
    async for c in storage.update_crons(
        filter_=CronFilter(id={cron1.id}),
        data=CronUpdate(enabled=False),
    ):
        updated = c
    assert updated is not None
    assert updated.enabled is False

    updated_crons = [
        c
        async for c in storage.update_crons(
            filter_=CronFilter(user_id={user.id}),
            data=CronUpdate(args={"key": "value"}),
        )
    ]
    assert len(updated_crons) == 2
    for c in updated_crons:
        assert c.args == {"key": "value"}

    await storage.delete_cron(filter_=CronFilter(id={cron1.id}))
    assert await storage.get_cron(filter_=CronFilter(id={cron1.id})) is None

    await storage.delete_crons(filter_=CronFilter(enabled=False))
    crons = [c async for c in storage.get_crons()]
    assert len(crons) == 0


async def assert_pagination_and_sort(storage: UsersStorageInterface) -> None:
    await storage.create_user(data=UserCreate(role=UserRoleEnum.USER))
    await storage.create_user(data=UserCreate(role=UserRoleEnum.ADMIN))
    await storage.create_user(data=UserCreate(role=UserRoleEnum.USER))

    users = [
        u
        async for u in storage.get_users(pagination=OffsetPagination(limit=2, offset=0))
    ]
    assert len(users) == 2

    users = [
        u
        async for u in storage.get_users(pagination=OffsetPagination(limit=2, offset=2))
    ]
    assert len(users) == 1

    users = [
        u
        async for u in storage.get_users(
            sort=BaseSort(sort_by="role", sort_by_order=SortByOrder.desc)
        )
    ]
    for i in range(len(users) - 1):
        assert users[i].role.value >= users[i + 1].role.value


async def assert_delete_users_filter(storage: UsersStorageInterface) -> None:
    await storage.create_user(data=UserCreate(role=UserRoleEnum.USER))
    admin = await storage.create_user(data=UserCreate(role=UserRoleEnum.ADMIN))
    await storage.create_user(data=UserCreate(role=UserRoleEnum.USER))

    await storage.delete_users(filter_=UserFilter(role={UserRoleEnum.USER}))
    users = [u async for u in storage.get_users()]
    assert len(users) == 1
    assert users[0].id == admin.id
