"""Worker: de tempos em tempos (polling) olha as filas do Jira e leva cada chamado de ponta a ponta.

Cada rodada (ciclo) tem duas etapas, uma por fila:

  1. TRIAGEM   chamados em "Novo"
               agente analisa -> grava categoria/decisão/prioridade + comentário JSON + Description
               automatizar -> "Fila Automação"
               humano      -> "Aguardando Revisão Humana" (passando por "Falhou" se for falha de dado)

  2. EXECUÇÃO  chamados em "Fila Automação"
               "Em Execução" -> robô (Calculadora ou Formulário) -> anexa evidências
               sucesso -> "Concluído"
               erro    -> "Falhou" -> "Aguardando Revisão Humana"

Falha em um chamado nunca derruba o worker: ela é registrada, o chamado vai para o humano
e o loop segue para o próximo.

Uso (na raiz do projeto):
    uv run python -m src.worker               # roda sem parar, a cada 15 s
    uv run python -m src.worker --intervalo 30
"""

import argparse
import logging
import time
from collections.abc import Callable

from src.agent.agente import analisar
from src.agent.resposta import montar_descricao
from src.models.agente import Analise, Atividade
from src.service.consulta import consultar
from src.service.registro import buscar_analise, salvar_analise
from src.service.calculadora import calcular
from src.models.rpa import CalculoForm, PedidoForm, RpaResult
from src.service.pw_forms import preencher_formulario
from src.models.ticket import Ticket
from src.service.jira_client import JiraClient, JiraError

log = logging.getLogger("worker")

# Status exatos do fluxo (CLAUDE.md)
NOVO = "Novo"
FILA = "Fila Automação"
EM_EXECUCAO = "Em Execução"
HUMANO = "Aguardando Revisão Humana"
CONCLUIDO = "Concluído"
FALHOU = "Falhou"

INTERVALO_PADRAO = 15  # segundos entre rodadas


# ------------------------------------------------------------------ passos reutilizados


def _enviar_ao_humano(jira: JiraClient, chamado: str, falha: bool) -> None:
    """Falha de dado/robô passa por 'Falhou' antes; decisão humana vai direto."""
    if falha:
        jira.transition_to(chamado, FALHOU)
    jira.transition_to(chamado, HUMANO)


def _anexar(jira: JiraClient, chamado: str, caminho: str) -> None:
    try:
        jira.attach(chamado, caminho)
    except (JiraError, OSError) as exc:  # evidência perdida não pode travar o chamado
        log.warning("[%s] não consegui anexar %s: %s", chamado, caminho, exc)


def _rodar_robo(analise: Analise, chamado: str) -> RpaResult:
    """Chama o robô da atividade. Os robôs já devolvem RpaResult sem levantar exceção;
    o try/except aqui é só a última barreira."""
    dados = {k: v.strip() if isinstance(v, str) else v for k, v in analise.dados_extraidos.items()}
    try:
        if analise.atividade is Atividade.CALCULADORA:
            return calcular(CalculoForm(**dados), ticket=chamado)
        if analise.atividade is Atividade.FORMULARIO:
            return preencher_formulario(PedidoForm(**dados), ticket=chamado)
        if analise.atividade is Atividade.CONSULTA:
            filtros = [(f["coluna"], f["valor"]) for f in dados.get("filtros", [])]
            return consultar(dados.get("colunas", []), filtros, ticket=chamado)
    except Exception as exc:  # noqa: BLE001
        log.exception("[%s] erro inesperado no robô", chamado)
        return RpaResult(success=False, message=f"erro inesperado no robô: {exc}")
    return RpaResult(success=False, message=f"atividade sem robô: {analise.atividade}")


# ------------------------------------------------------------------ etapa 1: triagem


def triar(jira: JiraClient, ticket: Ticket) -> None:
    """Chamado 'Novo': o agente analisa e o chamado segue para a fila certa."""
    chamado = ticket.key
    analise = analisar(ticket)
    salvar_analise(analise)

    automatizar = analise.decisao == "automatizar"
    jira.update_fields(
        chamado,
        categoria=analise.categoria,
        decisao="Automatizar" if automatizar else "Decisão Humana",
        priority=analise.prioridade,
    )
    jira.add_json_comment(chamado, analise.model_dump(mode="json"), title="Análise do agente")
    jira.set_description(chamado, montar_descricao(analise))

    if automatizar:
        jira.transition_to(chamado, FILA)
    else:
        _enviar_ao_humano(jira, chamado, falha=analise.falha)
    log.info("[%s] triagem concluída: %s", chamado, "fila de automação" if automatizar else "revisão humana")


# ------------------------------------------------------------------ etapa 2: execução


def executar(jira: JiraClient, ticket: Ticket) -> None:
    """Chamado 'Fila Automação': roda o robô e devolve o resultado ao Jira."""
    chamado = ticket.key
    jira.transition_to(chamado, EM_EXECUCAO)

    # usa a análise que aprovou o chamado; se não achar (ex.: registro apagado), analisa de novo
    analise = buscar_analise(chamado) or analisar(ticket)
    if analise.decisao != "automatizar":
        jira.set_description(chamado, montar_descricao(analise))
        _enviar_ao_humano(jira, chamado, falha=analise.falha)
        return

    rpa = _rodar_robo(analise, chamado)
    for caminho in rpa.evidencias:
        _anexar(jira, chamado, caminho)
    jira.set_description(chamado, montar_descricao(analise, rpa))

    if rpa.success:
        jira.transition_to(chamado, CONCLUIDO)
        log.info("[%s] concluído: %s", chamado, rpa.message)
    else:
        jira.add_comment(chamado, f"Falha do robô: {rpa.message}")
        _enviar_ao_humano(jira, chamado, falha=True)
        log.warning("[%s] robô falhou, enviado ao humano: %s", chamado, rpa.message)


# ------------------------------------------------------------------ loop


def _processar(jira: JiraClient, ticket: Ticket, etapa: Callable[[JiraClient, Ticket], None]) -> None:
    """Roda a etapa em um chamado. Qualquer erro vira log + envio ao humano; nunca sobe."""
    try:
        etapa(jira, ticket)
    except Exception as exc:  # noqa: BLE001
        log.exception("[%s] erro na etapa %s", ticket.key, etapa.__name__)
        try:
            jira.add_comment(ticket.key, f"Erro do sistema ao processar o chamado: {exc}")
            _enviar_ao_humano(jira, ticket.key, falha=True)
        except Exception:  # noqa: BLE001  (Jira fora do ar: o chamado fica na fila e é tentado de novo)
            log.exception("[%s] não consegui nem enviar ao humano", ticket.key)


def ciclo(jira: JiraClient) -> None:
    """Uma rodada: triagem dos 'Novo' e depois execução da 'Fila Automação'."""
    for status, etapa in ((NOVO, triar), (FILA, executar)):
        try:
            tickets = jira.tickets_in_status(status)
        except JiraError as exc:
            log.error("[-] não consegui listar '%s': %s", status, exc)
            continue
        if tickets:
            log.info("[-] %d chamado(s) em '%s'", len(tickets), status)
        for ticket in tickets:
            _processar(jira, ticket, etapa)


def main() -> None:
    parser = argparse.ArgumentParser(description="Worker de chamados (polling no Jira)")
    parser.add_argument("--intervalo", type=int, default=INTERVALO_PADRAO, help="segundos entre rodadas")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    jira = JiraClient()
    log.info("[-] worker iniciado (intervalo=%ss)", args.intervalo)
    try:
        while True:
            ciclo(jira)
            time.sleep(args.intervalo)
    except KeyboardInterrupt:
        log.info("[-] worker interrompido pelo usuário")
    finally:
        jira.close()


if __name__ == "__main__":
    main()
