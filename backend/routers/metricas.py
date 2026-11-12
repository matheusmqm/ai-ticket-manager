import logging

from fastapi import APIRouter, Depends, HTTPException

from backend.deps import get_jira, todos_chamados
from backend.metricas import calcular
from src.service.jira_client import JiraClient, JiraError

log = logging.getLogger("backend.metricas")
router = APIRouter(prefix="/metricas", tags=["metricas"])


@router.get("")
def metricas(jira: JiraClient = Depends(get_jira)) -> dict:
    try:
        tickets = todos_chamados(jira)
    except JiraError as exc:
        log.error("falha no Jira: %s", exc)
        raise HTTPException(502, "Não foi possível falar com o Jira") from exc
    return calcular(tickets)
