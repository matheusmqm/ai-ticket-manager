from typing import Literal

from pydantic import BaseModel, Field

Area = Literal["RH", "Operations", "Comercial"]


class NovoChamado(BaseModel):
    summary: str = Field(min_length=3, max_length=255)
    area: Area


class ChamadoResumo(BaseModel):
    key: str
    summary: str
    status: str
    area: str | None = None
    categoria: str | None = None
    decisao: str | None = None
    priority: str | None = None
    created: str | None = None
    passou_por_falhou: bool = False


class AnexoInfo(BaseModel):
    id: str
    filename: str
    mime_type: str = ""


class ChamadoDetalhe(ChamadoResumo):
    description: str = ""
    anexos: list[AnexoInfo] = []
