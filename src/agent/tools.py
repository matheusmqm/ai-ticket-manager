"""Ferramentas (tool calling) que o LLM escolhe. Escolher a ferramenta = rotear a atividade.

Os campos de dados aceitam null: o modelo deve dizer que falta o dado em vez de inventar.
Quem decide se o dado basta é o código (src/service/regras.py).
"""

from typing import Any

from src.models.agente import Atividade
from src.service.regras import COLUNAS_PEDIDOS

COMUNS: dict[str, Any] = {
    "prioridade": {
        "type": "string",
        "enum": ["Highest", "High", "Medium", "Low", "Lowest"],
        "description": "Prioridade sugerida. Use Medium se o chamado não indicar urgência.",
    },
    "resumo": {"type": "string", "description": "Resumo do pedido em uma frase."},
    "justificativa": {"type": "string", "description": "Motivo da escolha em UMA frase curta (até 20 palavras), escrita para o solicitante do chamado, sem jargão."},
    "confianca": {"type": "number", "description": "Confiança de 0 a 1."},
    "referencias_chamados": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Todos os IDs de chamados citados no texto (ex.: ID-12). Lista vazia se não houver.",
    },
    "acao_ampla": {
        "type": "boolean",
        "description": "true se o pedido afeta vários chamados, uma área inteira ou é uma ação em massa/sensível.",
    },
}

NULO_SE_AUSENTE = "Use null se o chamado não informar este dado. Nunca invente."


def _str_nulo(descricao: str) -> dict[str, Any]:
    return {"type": ["string", "null"], "description": f"{descricao} {NULO_SE_AUSENTE}"}


def _ferramenta(nome: str, descricao: str, dados: dict[str, Any] | None) -> dict[str, Any]:
    props = dict(COMUNS)
    required = list(COMUNS)
    if dados is not None:
        props["dados"] = {
            "type": "object",
            "properties": dados,
            "required": list(dados),
            "additionalProperties": False,
        }
        required.append("dados")
    return {
        "name": nome,
        "description": descricao,
        "strict": True,
        "input_schema": {"type": "object", "properties": props, "required": required, "additionalProperties": False},
    }


FERRAMENTAS: list[dict[str, Any]] = [
    _ferramenta(
        "calcular_na_calculadora",
        "O chamado pede uma conta aritmética simples entre dois números (soma, subtração, "
        "multiplicação ou divisão) para ser feita na Calculadora do Windows.",
        {
            "a": _str_nulo("Primeiro número, só dígitos com sinal e vírgula/ponto decimal (ex.: '12,5')."),
            "b": _str_nulo("Segundo número, no mesmo formato."),
            "operacao": {
                "anyOf": [{"type": "string", "enum": ["+", "-", "*", "/"]}, {"type": "null"}],
                "description": f"Operação: + - * /. {NULO_SE_AUSENTE}",
            },
        },
    ),
    _ferramenta(
        "preencher_formulario_pedido",
        "O chamado pede para registrar um pedido no formulário web de pedidos. "
        "O formulário exige cliente, valor do pedido, quantidade de produtos e empresa.",
        {
            "cliente": _str_nulo("Nome do cliente."),
            "valor_pedido": _str_nulo("Valor do pedido, só dígitos com vírgula/ponto decimal (ex.: '1432,40')."),
            "qtd_produtos": _str_nulo("Quantidade de produtos, número inteiro."),
            "empresa": _str_nulo("Empresa, exatamente como escrita no chamado (o formulário aceita COMP, ENG ou DESK)."),
        },
    ),
    _ferramenta(
        "consultar_pedidos",
        "O chamado pede para consultar informações de pedidos (ex.: status de um pedido) na base de pedidos. "
        f"Colunas da base: {', '.join(sorted(COLUNAS_PEDIDOS))}. Use esses nomes quando o chamado se referir "
        "claramente a uma delas (ex.: 'pedidos do cliente Jonas' -> cliente = Jonas). Se o chamado pedir algo que não está "
        "nessa lista, copie o nome como o solicitante escreveu; não troque por outra coluna.",
        {
            "colunas": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Colunas que o chamado quer ver, com o nome que o solicitante usou. Lista vazia se não disser.",
            },
            "filtros": {
                "type": "array",
                "description": "Condições da consulta, uma por critério citado no chamado (ex.: cliente = Jonas).",
                "items": {
                    "type": "object",
                    "properties": {"coluna": {"type": "string"}, "valor": {"type": "string"}},
                    "required": ["coluna", "valor"],
                    "additionalProperties": False,
                },
            },
        },
    ),
    _ferramenta(
        "encaminhar_para_humano",
        "Use quando o chamado for ambíguo, estiver fora do escopo das outras ferramentas, não for um dos "
        "pedidos automatizáveis, ou pedir algo amplo/sensível. Explique o motivo na justificativa.",
        None,
    ),
]

FERRAMENTA_PARA_ATIVIDADE: dict[str, Atividade] = {
    "calcular_na_calculadora": Atividade.CALCULADORA,
    "preencher_formulario_pedido": Atividade.FORMULARIO,
    "consultar_pedidos": Atividade.CONSULTA,
    "encaminhar_para_humano": Atividade.HUMANO,
}
