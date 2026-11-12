from pydantic import BaseModel


class Anexo(BaseModel):
    id: str
    filename: str
    mime_type: str = ""


class Ticket(BaseModel):
    key: str
    summary: str
    description: str = ""
    status: str
    priority: str | None = None
    area: str | None = None
    categoria: str | None = None
    decisao: str | None = None
    created: str | None = None
    # preenchidos só quando a busca pede o histórico (expand=changelog)
    passou_por_falhou: bool = False
    anexos: list[Anexo] = []

    @property
    def text(self) -> str:
        """Texto do pedido para o agente: só o Summary.

        A Description é a resposta do sistema (resultado, erro ou motivo do encaminhamento
        ao humano), então nunca entra como entrada.
        """
        return self.summary.strip()
