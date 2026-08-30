from unittest.mock import MagicMock

import pytest

from microclaw.channels.fabric import get_channel
from microclaw.channels.settings import ChannelSettings
from microclaw.channels.vk.settings import VKSettings


class TestGetChannel:
    def test_vk(self, agent, sessions_storage, syncer, users_storage, resolver):
        from microclaw.channels.vk.base import BaseVKChannel

        settings = VKSettings(token="fake-token")
        result = get_channel(
            settings=settings,
            agent=agent,
            sessions_storage=sessions_storage,
            syncer=syncer,
            users_storage=users_storage,
            resolver=resolver,
        )
        assert isinstance(result, BaseVKChannel)

    def test_unsupported_raises(
        self, agent, sessions_storage, syncer, users_storage, resolver
    ):
        class FakeType:
            value = "fake"

        settings = MagicMock(spec=ChannelSettings)
        settings.type = FakeType()

        with pytest.raises(ValueError, match="Unsupported channel type"):
            get_channel(
                settings=settings,
                agent=agent,
                sessions_storage=sessions_storage,
                syncer=syncer,
                users_storage=users_storage,
                resolver=resolver,
            )
