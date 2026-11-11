from pydantic import BaseModel


class RpaResult(BaseModel):
    """Contrato único de retorno dos robôs (web e desktop)."""

    success: bool
    message: str
    evidencias: list[str] = []
