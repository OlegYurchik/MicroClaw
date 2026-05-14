import fastapi


class HTTPException(fastapi.HTTPException):
    def __init__(self, detail: str | None = None):
        super().__init__(
            status_code=self.STATUS_CODE,
            detail=detail or self.DETAIL,
        )

    @property
    def STATUS_CODE(self):
        raise NotImplementedError

    @property
    def DETAIL(self):
        raise NotImplementedError


class HTTPUnauthorized(HTTPException):
    STATUS_CODE = fastapi.status.HTTP_401_UNAUTHORIZED
    DETAIL = "Unauthorized."


class HTTPForbidden(HTTPException):
    STATUS_CODE = fastapi.status.HTTP_403_FORBIDDEN
    DETAIL = "Forbidden."


class HTTPNotFound(HTTPException):
    STATUS_CODE = fastapi.status.HTTP_404_NOT_FOUND
    DETAIL = "Not found."


class HTTPNotImplemented(HTTPException):
    STATUS_CODE = fastapi.status.HTTP_501_NOT_IMPLEMENTED
    DETAIL = "Not implemented."
