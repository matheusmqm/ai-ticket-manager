"""Agregação das métricas a partir dos chamados do Jira. Função pura: não chama o Jira nem grava nada."""

from collections import Counter

from src.models.ticket import Ticket

AUTOMATIZAR = "Automatizar"
HUMANO = "Decisão Humana"
CONCLUIDO = "Concluído"
SEM_CATEGORIA = "Sem categoria"


def _pct(parte: int, total: int) -> float:
    return round(100 * parte / total, 1) if total else 0.0


def calcular(tickets: list[Ticket]) -> dict:
    """Decisão vem do campo Decisão; automação do campo Categoria; erro do histórico (passou por 'Falhou')."""
    total = len(tickets)
    triados = [t for t in tickets if t.decisao in (AUTOMATIZAR, HUMANO)]
    n_triados = len(triados)
    automatizados = sum(t.decisao == AUTOMATIZAR for t in triados)
    humanos = n_triados - automatizados
    com_erro = [t for t in tickets if t.passou_por_falhou]

    return {
        "total": total,
        "triados": n_triados,
        "aguardando_triagem": total - n_triados,
        "decisao": {
            "automatizar": automatizados,
            "humano": humanos,
            "pct_automatizar": _pct(automatizados, n_triados),
            "pct_humano": _pct(humanos, n_triados),
        },
        "por_automacao": dict(Counter(t.categoria or SEM_CATEGORIA for t in tickets)),
        "por_status": dict(Counter(t.status for t in tickets)),
        "concluidos": sum(t.status == CONCLUIDO for t in tickets),
        "pct_concluidos": _pct(sum(t.status == CONCLUIDO for t in tickets), total),
        "erros": {
            "total": len(com_erro),
            "pct": _pct(len(com_erro), total),
            "por_automacao": dict(Counter(t.categoria or SEM_CATEGORIA for t in com_erro)),
        },
    }
