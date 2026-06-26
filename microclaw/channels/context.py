import contextvars

REQUEST_ID_CONTEXT = contextvars.ContextVar("request_id", default=None)
