from .dto import SessionData
from .tables import MessageTable, SessionTable
from metaorm import BaseRepository

from microclaw.dto import AgentMessage
from microclaw.sessions_storages.filters import MessageFilter, SessionFilter


class SessionsRepository(BaseRepository, table=SessionTable, filter_=SessionFilter, dto=SessionData):
    pass


class MessagesRepository(
    BaseRepository, table=MessageTable, filter_=MessageFilter, dto=AgentMessage
):
    pass
