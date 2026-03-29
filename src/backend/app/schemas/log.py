"""Schematy Pydantic dla endpointu logów."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.log import LogSeverity


class LogResponse(BaseModel):
    """Pojedynczy wpis logu zwracany przez API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    logged_at: datetime
    vhost: str
    severity: LogSeverity
    message: str


class LogListResponse(BaseModel):
    """Strona wyników dla GET /logs.

    Zwracamy listę plus metadane paginacji, żeby frontend wiedział:
    - ile rekordów istnieje łącznie
    - którą stronę właśnie dostał
    - ile rekordów ma jedna strona
    """

    items: list[LogResponse]
    total: int
    page: int
    page_size: int
