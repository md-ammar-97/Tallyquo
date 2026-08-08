from pydantic import BaseModel


class YearEndPackOut(BaseModel):
    url: str
    filename: str
    expires_in_seconds: int
    byte_size: int
