from .tables import (
    CronTable,
    TokenTable,
    UserChannelTable,
    UserTable,
    WebhookTable,
)
from metaorm import BaseRepository

from microclaw.dto import CronTask, Token, User, UserChannel, Webhook
from microclaw.users_storages.filters import (
    CronFilter,
    TokenFilter,
    UserChannelFilter,
    UserFilter,
    WebhookFilter,
)


class UsersRepository(BaseRepository, table=UserTable, filter_=UserFilter, dto=User):
    pass


class UserChannelsRepository(
    BaseRepository,
    table=UserChannelTable,
    filter_=UserChannelFilter,
    dto=UserChannel,
):
    pass


class CronsRepository(BaseRepository, table=CronTable, filter_=CronFilter, dto=CronTask):
    pass


class TokensRepository(BaseRepository, table=TokenTable, filter_=TokenFilter, dto=Token):
    pass


class WebhooksRepository(BaseRepository, table=WebhookTable, filter_=WebhookFilter, dto=Webhook):
    pass
