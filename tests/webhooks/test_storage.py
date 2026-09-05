import uuid

import pytest

from microclaw.dto import Webhook
from microclaw.users_storages.dto import UserCreate, WebhookCreate
from microclaw.users_storages.filters import UserFilter, WebhookFilter
from microclaw.users_storages.memory.settings import MemoryUsersStorageSettings
from microclaw.users_storages.memory.storage import MemoryUsersStorage


@pytest.fixture
def storage():
    return MemoryUsersStorage(settings=MemoryUsersStorageSettings())


class TestMemoryUsersStorageWebhooks:
    @pytest.mark.asyncio
    async def test_create_and_get_webhook(self, storage):
        user_id = uuid.uuid4()
        webhook = Webhook(
            id=uuid.uuid4(),
            path="test.path",
            enabled=True,
            args={"key": "val"},
        )
        await storage.create_webhook(
            data=WebhookCreate(
                user_id=user_id,
                id=webhook.id,
                path=webhook.path,
                enabled=webhook.enabled,
                args=webhook.args,
            )
        )

        webhooks = [w async for w in storage.get_webhooks()]
        assert len(webhooks) == 1
        assert webhooks[0].id == webhook.id

    @pytest.mark.asyncio
    async def test_get_webhooks_filter_by_user_id(self, storage):
        user1 = uuid.uuid4()
        user2 = uuid.uuid4()

        await storage.create_webhook(
            data=WebhookCreate(
                user_id=user1,
                id=uuid.uuid4(),
                path="a",
                enabled=True,
                args={},
            )
        )
        await storage.create_webhook(
            data=WebhookCreate(
                user_id=user2,
                id=uuid.uuid4(),
                path="b",
                enabled=True,
                args={},
            )
        )

        webhooks = [w async for w in storage.get_webhooks(filter_=WebhookFilter(user_id={user1}))]
        assert len(webhooks) == 1
        assert webhooks[0].path == "a"

    @pytest.mark.asyncio
    async def test_get_webhooks_filter_by_id(self, storage):
        user_id = uuid.uuid4()
        webhook = Webhook(id=uuid.uuid4(), path="a", enabled=True, args={})
        await storage.create_webhook(
            data=WebhookCreate(
                user_id=user_id,
                id=webhook.id,
                path=webhook.path,
                enabled=webhook.enabled,
                args=webhook.args,
            )
        )

        webhooks = [w async for w in storage.get_webhooks(filter_=WebhookFilter(id={webhook.id}))]
        assert len(webhooks) == 1
        assert webhooks[0].path == "a"

    @pytest.mark.asyncio
    async def test_get_webhooks_filter_by_enabled(self, storage):
        user_id = uuid.uuid4()
        await storage.create_webhook(
            data=WebhookCreate(
                user_id=user_id,
                id=uuid.uuid4(),
                path="a",
                enabled=True,
                args={},
            )
        )
        await storage.create_webhook(
            data=WebhookCreate(
                user_id=user_id,
                id=uuid.uuid4(),
                path="b",
                enabled=False,
                args={},
            )
        )

        webhooks = [w async for w in storage.get_webhooks(filter_=WebhookFilter(enabled=True))]
        assert len(webhooks) == 1
        assert webhooks[0].path == "a"

    @pytest.mark.asyncio
    async def test_remove_webhook(self, storage):
        user_id = uuid.uuid4()
        webhook = Webhook(id=uuid.uuid4(), path="a", enabled=True, args={})
        await storage.create_webhook(
            data=WebhookCreate(
                user_id=user_id,
                id=webhook.id,
                path=webhook.path,
                enabled=webhook.enabled,
                args=webhook.args,
            )
        )

        await storage.delete_webhook(filter_=WebhookFilter(id={webhook.id}))

        webhooks = [w async for w in storage.get_webhooks()]
        assert len(webhooks) == 0

    @pytest.mark.asyncio
    async def test_delete_user_removes_webhooks(self, storage):
        user = await storage.create_user(data=UserCreate())
        await storage.create_webhook(
            data=WebhookCreate(
                user_id=user.id,
                id=uuid.uuid4(),
                path="a",
                enabled=True,
                args={},
            )
        )

        await storage.delete_user(filter_=UserFilter(id={user.id}))

        webhooks = [w async for w in storage.get_webhooks()]
        assert len(webhooks) == 0
