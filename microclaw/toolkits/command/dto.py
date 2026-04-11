from pydantic import BaseModel


class CommandResult(BaseModel):
    stdout: str
    stderr: str
    return_code: int
