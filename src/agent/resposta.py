"""Texto curto que vai na Description do chamado depois da análise/execução.

O solicitante escreve só o Summary; a Description é a resposta do sistema:
resultado da automação, motivo da falha ou motivo do encaminhamento ao humano.
"""

from src.agent.schema import Analise, Atividade
from src.rpa.models import RpaResult

ENCAMINHADO = "O chamado foi encaminhado para revisão humana."


def _sucesso(analise: Analise, rpa: RpaResult) -> str:
    d = analise.dados_extraidos
    if analise.atividade is Atividade.CALCULADORA:
        return f"Resultado: {rpa.message}."
    if analise.atividade is Atividade.FORMULARIO:
        return (
            f"Pedido registrado no formulário: cliente {d.get('cliente')}, valor {d.get('valor_pedido')}, "
            f"{d.get('qtd_produtos')} produto(s), empresa {d.get('empresa')}."
        )
    return f"Resultado da consulta: {rpa.message}"


def montar_descricao(analise: Analise, rpa: RpaResult | None = None) -> str:
    """Monta a Description. `rpa` é o resultado da execução; sem ele, descreve só a análise."""
    if rpa is not None:
        if rpa.success:
            return _sucesso(analise, rpa)
        return f"Falha na execução da automação: {rpa.message}\n{ENCAMINHADO}"

    if analise.falha and analise.atividade is Atividade.HUMANO:
        # falha do próprio agente (API fora, resposta inválida): detalhe técnico fica só no log
        return f"Não foi possível analisar o chamado (erro técnico, ver log).\n{ENCAMINHADO}"

    if analise.falha:
        return f"Não foi possível automatizar: {'; '.join(analise.erros)}.\n{ENCAMINHADO}"

    if analise.decisao == "humano":
        motivos = [analise.justificativa.rstrip("."), *analise.alertas]
        return f"Esta solicitação não pode ser feita pela automação: {'; '.join(motivos)}.\n{ENCAMINHADO}"

    return "Chamado aprovado para a automação."
