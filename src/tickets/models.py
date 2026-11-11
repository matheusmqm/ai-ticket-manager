from pydantic import BaseModel


class Ticket(BaseModel):
    key: str
    summary: str
    description: str = ""
    status: str
    priority: str | None = None
    area: str | None = None
    categoria: str | None = None
    decisao: str | None = None

    @property
    def text(self) -> str:
        """Texto-base do pedido: Summary + Description."""
        return f"{self.summary}\n{self.description}".strip()
