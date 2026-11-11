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
        """Texto do pedido para o agente: só o Summary.

        A Description é a resposta do sistema (resultado, erro ou motivo do encaminhamento
        ao humano), então nunca entra como entrada.
        """
        return self.summary.strip()
