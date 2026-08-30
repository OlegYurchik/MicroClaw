import uuid

import pytest

from microclaw.dto import CronTask, UserRoleEnum
from microclaw.toolkits import ToolKitSettings
from microclaw.toolkits.accessors import AllUsersAccessor
from microclaw.toolkits.context import TOOLKIT_CONTEXT, ToolkitExecutionContext
from microclaw.toolkits.cron.toolkit import CronToolKit
from microclaw.toolkits.enums import PermissionModeEnum
from microclaw.users_storages.dto import CronCreate, UserCreate
from microclaw.users_storages.filters import CronFilter


@pytest.fixture
def make_cron_toolkit():
    def _make(
        create_mode=PermissionModeEnum.REQUEST,
        delete_mode=PermissionModeEnum.REQUEST,
    ):
        settings = ToolKitSettings(
            path="microclaw.toolkits.cron.toolkit.CronToolKit",
            args={
                "create_mode": (
                    create_mode.value
                    if isinstance(create_mode, PermissionModeEnum)
                    else create_mode
                ),
                "delete_mode": (
                    delete_mode.value
                    if isinstance(delete_mode, PermissionModeEnum)
                    else delete_mode
                ),
            },
        )
        return CronToolKit(key="cron", settings=settings)

    return _make


# ─── get_crons ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_crons_current_user(
    toolkit_context, users_storage, make_cron_toolkit
):
    toolkit = make_cron_toolkit()
    user_id = toolkit_context.current_user_accessor.user_id

    cron1 = await users_storage.create_cron(
        data=CronCreate(user_id=user_id, path="a.b", cron="*/5 * * * *")
    )
    cron2 = await users_storage.create_cron(
        data=CronCreate(user_id=user_id, path="c.d", cron="0 0 * * *", enabled=False)
    )

    result = await toolkit.get_crons()
    assert len(result) == 2
    ids = {c.id for c in result}
    assert cron1.id in ids
    assert cron2.id in ids


@pytest.mark.asyncio
async def test_get_crons_cross_user_allowed(
    toolkit_context, users_storage, make_cron_toolkit
):
    toolkit = make_cron_toolkit()
    other_user = await users_storage.create_user(
        data=UserCreate(role=UserRoleEnum.USER)
    )

    cron = await users_storage.create_cron(
        data=CronCreate(user_id=other_user.id, path="x.y", cron="0 1 * * *")
    )

    result = await toolkit.get_crons(user_id=str(other_user.id))
    assert len(result) == 1
    assert result[0].id == cron.id


@pytest.mark.asyncio
async def test_get_crons_cross_user_denied(
    toolkit_context, users_storage, make_cron_toolkit
):
    toolkit = make_cron_toolkit()
    other_user = await users_storage.create_user(
        data=UserCreate(role=UserRoleEnum.USER)
    )

    context_no_accessor = ToolkitExecutionContext(
        session_id=toolkit_context.session_id,
        request_id=toolkit_context.request_id,
        channel_key=toolkit_context.channel_key,
        channel_internal_id=toolkit_context.channel_internal_id,
        current_user_accessor=toolkit_context.current_user_accessor,
        all_users_accessor=None,
    )
    token = TOOLKIT_CONTEXT.set(context_no_accessor)
    try:
        with pytest.raises(PermissionError, match="Cross-user access not granted"):
            await toolkit.get_crons(user_id=str(other_user.id))
    finally:
        TOOLKIT_CONTEXT.reset(token)


# ─── create_cron ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_cron_success(toolkit_context, users_storage, make_cron_toolkit):
    toolkit = make_cron_toolkit(create_mode=PermissionModeEnum.ALLOW)

    result = await toolkit.create_cron(
        path="microclaw.cron.tasks.test.Test",
        cron="0 2 * * *",
        enabled=True,
        args={"key": "value"},
    )

    assert isinstance(result, CronTask)
    assert result.path == "microclaw.cron.tasks.test.Test"
    assert result.cron == "0 2 * * *"
    assert result.enabled is True
    assert result.args == {"key": "value"}

    user_id = toolkit_context.current_user_accessor.user_id
    crons = [
        c async for c in users_storage.get_crons(filter_=CronFilter(user_id={user_id}))
    ]
    assert len(crons) == 1
    assert crons[0].id == result.id


@pytest.mark.asyncio
async def test_create_cron_denied(toolkit_context, make_cron_toolkit):
    toolkit = make_cron_toolkit(create_mode=PermissionModeEnum.DENY)

    with pytest.raises(PermissionError, match="Operation denied by configuration"):
        await toolkit.create_cron(path="a.b", cron="* * * * *")


# ─── remove_cron ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_remove_cron_success(toolkit_context, users_storage, make_cron_toolkit):
    toolkit = make_cron_toolkit(delete_mode=PermissionModeEnum.ALLOW)
    user_id = toolkit_context.current_user_accessor.user_id

    cron = await users_storage.create_cron(
        data=CronCreate(user_id=user_id, path="a.b", cron="*/5 * * * *")
    )

    await toolkit.remove_cron(cron_id=str(cron.id))

    crons = [
        c async for c in users_storage.get_crons(filter_=CronFilter(user_id={user_id}))
    ]
    assert len(crons) == 0


@pytest.mark.asyncio
async def test_remove_cron_not_found(toolkit_context, users_storage, make_cron_toolkit):
    toolkit = make_cron_toolkit(delete_mode=PermissionModeEnum.ALLOW)
    other_user = await users_storage.create_user(
        data=UserCreate(role=UserRoleEnum.USER)
    )
    fake_cron_id = str(uuid.uuid4())

    with pytest.raises(ValueError, match="not found"):
        await toolkit.remove_cron(cron_id=fake_cron_id, user_id=str(other_user.id))


@pytest.mark.asyncio
async def test_remove_cron_cross_user_write_denied(
    toolkit_context, users_storage, make_cron_toolkit
):
    toolkit = make_cron_toolkit(delete_mode=PermissionModeEnum.ALLOW)
    other_user = await users_storage.create_user(
        data=UserCreate(role=UserRoleEnum.USER)
    )

    cron = await users_storage.create_cron(
        data=CronCreate(user_id=other_user.id, path="a.b", cron="*/5 * * * *")
    )

    context_readonly = ToolkitExecutionContext(
        session_id=toolkit_context.session_id,
        request_id=toolkit_context.request_id,
        channel_key=toolkit_context.channel_key,
        channel_internal_id=toolkit_context.channel_internal_id,
        current_user_accessor=toolkit_context.current_user_accessor,
        all_users_accessor=AllUsersAccessor(storage=users_storage, writable=False),
    )
    token = TOOLKIT_CONTEXT.set(context_readonly)
    try:
        with pytest.raises(
            PermissionError, match="Cross-user write access not granted"
        ):
            await toolkit.remove_cron(cron_id=str(cron.id), user_id=str(other_user.id))
    finally:
        TOOLKIT_CONTEXT.reset(token)
