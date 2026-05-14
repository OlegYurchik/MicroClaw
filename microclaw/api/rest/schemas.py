from pydantic import BaseModel


class ListResponse(BaseModel):
    data: list
