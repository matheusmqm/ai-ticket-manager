"""Modelos compartilhados do RPA. Sem dependência de Playwright/pywinauto, para que o
agente e a validação possam importá-los sem carregar os robôs."""

from typing import Literal

from pydantic import BaseModel, Field

EMPRESAS = ("COMP", "ENG", "DESK")


class RpaResult(BaseModel):
    """Contrato único de retorno dos robôs (web e desktop)."""

    success: bool
    message: str
    evidencias: list[str] = []


class PedidoForm(BaseModel):
    """Dados do formulário de pedido. Todos os campos são obrigatórios no Google Forms."""

    cliente: str = Field(min_length=1)
    valor_pedido: str = Field(pattern=r"^\d+([.,]\d{1,2})?$")
    qtd_produtos: str = Field(pattern=r"^\d+$")
    empresa: Literal["COMP", "ENG", "DESK"]


class CalculoForm(BaseModel):
    """Conta da Calculadora: dois números (com sinal e vírgula/ponto decimal) e uma operação."""

    a: str = Field(pattern=r"^-?\d+([.,]\d+)?$")
    b: str = Field(pattern=r"^-?\d+([.,]\d+)?$")
    operacao: Literal["+", "-", "*", "/"]
