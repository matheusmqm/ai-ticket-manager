"""Agente de triagem: o LLM escolhe a ferramenta (atividade) e extrai os dados;
o código valida os detalhes e decide. analisar() nunca levanta exceção."""

import logging

import anthropic
from pydantic import ValidationError

from src.agent.prompt import SYSTEM, montar_pedido
from src.models.agente import CATEGORIA_POR_ATIVIDADE, Analise, Atividade, Proposta
from src.agent.tools import FERRAMENTA_PARA_ATIVIDADE, FERRAMENTAS
from src.config import get_settings
from src.models.ticket import Ticket
from src.service.regras import validar_alertas, validar_dados

log = logging.getLogger("agente")

MAX_TOKENS = 4096
LIMIAR_CONFIANCA = 0.6  # abaixo disso, o chamado vai para revisão humana


class AgenteError(Exception):
    """Falha da chamada ao LLM ou resposta fora do contrato."""


class RespostaInvalida(AgenteError):
    """O LLM respondeu, mas fora do contrato (sem ferramenta, JSON fora do schema). Vale repetir."""


def _cliente() -> anthropic.Anthropic:
    chave = get_settings().anthropic_api_key
    if chave is None:
        raise AgenteError("ANTHROPIC_API_KEY não configurada")
    return anthropic.Anthropic(api_key=chave.get_secret_value())


def _chamar_llm(ticket: Ticket, client: anthropic.Anthropic | None) -> tuple[Atividade, Proposta]:
    client = client or _cliente()
    try:
        resp = client.messages.create(
            model=get_settings().anthropic_model,
            max_tokens=MAX_TOKENS,
            system=SYSTEM,
            tools=FERRAMENTAS,  # type: ignore[arg-type]
            tool_choice={"type": "auto", "disable_parallel_tool_use": True},
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": montar_pedido(ticket)}],
        )
    except anthropic.APIError as exc:
        raise AgenteError(f"falha na API do Claude: {exc}") from exc

    log.info("[%s] stop_reason=%s tokens=%s/%s", ticket.key, resp.stop_reason, resp.usage.input_tokens, resp.usage.output_tokens)
    usos = [b for b in resp.content if b.type == "tool_use"]
    if resp.stop_reason == "refusal" or len(usos) != 1:
        raise RespostaInvalida(f"resposta fora do contrato (stop_reason={resp.stop_reason}, chamadas de ferramenta={len(usos)})")

    uso = usos[0]
    atividade = FERRAMENTA_PARA_ATIVIDADE.get(uso.name)
    if atividade is None:
        raise RespostaInvalida(f"ferramenta desconhecida: {uso.name}")
    try:
        return atividade, Proposta(**uso.input)  # type: ignore[arg-type]
    except (ValidationError, TypeError) as exc:
        raise RespostaInvalida(f"campos fora do schema: {exc}") from exc


def _falha_do_agente(ticket: Ticket, motivo: str) -> Analise:
    return Analise(
        numero_chamado=ticket.key,
        area=ticket.area,
        categoria=CATEGORIA_POR_ATIVIDADE[Atividade.HUMANO],
        atividade=Atividade.HUMANO,
        prioridade="Medium",
        resumo=ticket.summary[:255],
        dados_extraidos={},
        decisao="humano",
        justificativa="O agente não conseguiu analisar o chamado.",
        confianca=0.0,
        falha=True,
        erros=[motivo],
    )


def analisar(
    ticket: Ticket, client: anthropic.Anthropic | None = None, limiar: float = LIMIAR_CONFIANCA
) -> Analise:
    """Analisa o chamado. Confiança abaixo do limiar bloqueia a automação (vai para o humano).
    A avaliação usa limiar=0 para medir o agente sem o limiar."""
    try:
        try:
            atividade, proposta = _chamar_llm(ticket, client)
        except RespostaInvalida as exc:
            log.warning("[%s] resposta fora do contrato, tentando de novo: %s", ticket.key, exc)
            atividade, proposta = _chamar_llm(ticket, client)
    except AgenteError as exc:
        log.error("[%s] agente falhou: %s", ticket.key, exc)
        return _falha_do_agente(ticket, str(exc))

    erros: list[str] = []
    alertas: list[str] = []
    if atividade is not Atividade.HUMANO:
        erros = validar_dados(atividade, proposta.dados)
        alertas = validar_alertas(ticket, proposta)
        if proposta.confianca < limiar:
            alertas.append(f"confiança {proposta.confianca:.2f} abaixo do limiar {limiar:.2f}")

    automatizar = atividade is not Atividade.HUMANO and not erros and not alertas
    analise = Analise(
        numero_chamado=ticket.key,
        area=ticket.area,
        categoria=CATEGORIA_POR_ATIVIDADE[atividade],
        atividade=atividade,
        prioridade=proposta.prioridade,
        resumo=proposta.resumo,
        dados_extraidos=proposta.dados,
        decisao="automatizar" if automatizar else "humano",
        justificativa=proposta.justificativa,
        confianca=proposta.confianca,
        falha=bool(erros),
        erros=erros,
        alertas=alertas,
    )
    log.info(
        "[%s] atividade=%s decisao=%s falha=%s confianca=%.2f erros=%s alertas=%s",
        ticket.key, atividade.value, analise.decisao, analise.falha, analise.confianca, erros, alertas,
    )
    return analise
