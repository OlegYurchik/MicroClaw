import uuid
from typing import AsyncGenerator

import facet

from microclaw.channels import ChannelTypeEnum
from microclaw.dto import User


class UsersStorageInterface(facet.AsyncioServiceMixin):
    async def create_user(self, user_id: uuid.UUID | None = None) -> User:
        pass

    async def get_user(self, user_id: uuid.UUID) -> User | None:
        pass

    async def get_user_sessions(self, user_id: uuid.UUID) -> AsyncGenerator[uuid.UUID]:
        pass

    async def get_user_by_channel_external_id(
            self,
            channel_type: ChannelTypeEnum,
            channel_external_id: uuid.UUID,
    ):
        pass
