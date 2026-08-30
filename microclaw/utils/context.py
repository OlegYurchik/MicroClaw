import contextlib
import contextvars
import uuid


SESSION_ID_CONTEXT = contextvars.ContextVar("session_id", default=None)
REQUEST_ID_CONTEXT = contextvars.ContextVar("request_id", default=None)


def get_current_request_id() -> uuid.UUID | None:
    return REQUEST_ID_CONTEXT.get(None)


def get_current_session_id() -> uuid.UUID | None:
    return SESSION_ID_CONTEXT.get(None)


@contextlib.contextmanager
def set_current_request_id(request_id: uuid.UUID):
    token = REQUEST_ID_CONTEXT.set(request_id)
    try:
        yield
    finally:
        REQUEST_ID_CONTEXT.reset(token)


@contextlib.contextmanager
def set_current_session_id(session_id: uuid.UUID):
    token = SESSION_ID_CONTEXT.set(session_id)
    try:
        yield
    finally:
        SESSION_ID_CONTEXT.reset(token)
