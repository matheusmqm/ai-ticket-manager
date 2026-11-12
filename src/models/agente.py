"""Schemas do agente: o que o LLM propõe (Proposta) e a análise final (Analise)."""

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Atividade(StrEnum):
    CALCULADORA = "calculadora"
    FORMULARIO = "formulario"
    CONSULTA = "consulta"
    HUMANO = "humano"


Categoria = Literal["Calculadora", "Consulta", "Inserção", "Humano"]
# Categoria (dropdown do Jira) = qual automação o chamado pede. Derivada da atividade em código,
# não escolhida pelo LLM. Quem separa "foi para o humano" é o campo Decisão.
CATEGORIA_POR_ATIVIDADE: dict[Atividade, Categoria] = {
    Atividade.CALCULADORA: "Calculadora",
    Atividade.CONSULTA: "Consulta",
    Atividade.FORMULARIO: "Inserção",
    Atividade.HUMANO: "Humano",
}
Prioridade = Literal["Highest", "High", "Medium", "Low", "Lowest"]


# --- Dados extraídos por atividade. Tudo é opcional: o LLM devolve null quando o
# --- chamado não traz o dado, e é o código (src/service/regras.py) que decide se falta algo.


class DadosCalculadora(BaseModel):
    a: str | None = None
    b: str | None = None
    operacao: str | None = None  # validada depois: "+", "-", "*" ou "/"


class DadosFormulario(BaseModel):
    cliente: str | None = None
    valor_pedido: str | None = None
    qtd_produtos: str | None = None
    empresa: str | None = None  # validada depois: COMP, ENG ou DESK


class Filtro(BaseModel):
    coluna: str
    valor: str


class DadosConsulta(BaseModel):
    colunas: list[str] = []  # colunas que o pedido quer ver
    filtros: list[Filtro] = []  # condições (ex.: pedido_id = 123)


class Proposta(BaseModel):
    """Campos comuns que o LLM preenche em qualquer ferramenta."""

    prioridade: Prioridade
    resumo: str
    justificativa: str
    confianca: float = Field(ge=0, le=1)
    referencias_chamados: list[str] = []
    acao_ampla: bool = False
    dados: dict[str, Any] = {}


class Analise(BaseModel):
    """Saída final do agente (regra 6 do CLAUDE.md), já validada pelo código."""

    numero_chamado: str
    area: str | None  # vem do Jira (dado confiável), não do LLM
    categoria: Categoria
    atividade: Atividade
    prioridade: Prioridade
    resumo: str
    dados_extraidos: dict[str, Any]
    decisao: Literal["automatizar", "humano"]
    justificativa: str
    confianca: float
    # erros: o chamado caiu numa atividade automatizável, mas não dá para executar
    # (dado faltando, valor inválido, coluna inexistente...). falha=True, e o worker
    # trata como Falhou -> Aguardando Revisão Humana.
    falha: bool = False
    erros: list[str] = []
    # alertas: regras que exigem humano sem ser falha de dado (inconsistência entre
    # chamados, ação ampla).
    alertas: list[str] = []
