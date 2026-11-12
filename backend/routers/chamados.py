import logging
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response

from backend.deps import cacheado, get_jira, invalidar_cache, todos_chamados
from backend.schemas import ChamadoDetalhe, ChamadoResumo, NovoChamado
from src.service.jira_client import JiraClient, JiraError

log = logging.getLogger("backend.chamados")
router = APIRouter(prefix="/chamados", tags=["chamados"])


def _erro_jira(exc: JiraError) -> HTTPException:
    if exc.status_code == 404:
        return HTTPException(404, "Chamado não encontrado")
    log.error("falha no Jira: %s", exc)
    return HTTPException(502, "Não foi possível falar com o Jira")


@router.get("", response_model=list[ChamadoResumo])
def listar(jira: JiraClient = Depends(get_jira)) -> list:
    try:
        return todos_chamados(jira)
    except JiraError as exc:
        raise _erro_jira(exc) from exc


@router.get("/{key}", response_model=ChamadoDetalhe)
def detalhar(key: str, jira: JiraClient = Depends(get_jira)):
    try:
        return jira.get_ticket(key)
    except JiraError as exc:
        raise _erro_jira(exc) from exc


@router.get("/{key}/anexos/{anexo_id}")
def baixar_anexo(key: str, anexo_id: str, jira: JiraClient = Depends(get_jira)) -> Response:
    """Entrega um anexo do chamado (o Jira exige login, então o navegador não acessa direto).
    Só serve anexos que pertencem ao chamado informado."""
    try:
        ticket = cacheado(f"ticket:{key}", lambda: jira.get_ticket(key))
        anexo = next((a for a in ticket.anexos if a.id == anexo_id), None)
        if anexo is None:
            raise HTTPException(404, "Anexo não encontrado")
        conteudo = jira.attachment_content(key, anexo_id)
    except JiraError as exc:
        raise _erro_jira(exc) from exc

    # imagens aparecem na tela; qualquer outro tipo (e SVG, que pode ter script) só baixa
    inline = anexo.mime_type.startswith("image/") and "svg" not in anexo.mime_type
    headers = {
        "Cache-Control": "private, max-age=3600",
        "X-Content-Type-Options": "nosniff",
        "Content-Disposition": f'{"inline" if inline else "attachment"}; filename="{quote(anexo.filename)}"',
    }
    return Response(conteudo, media_type=anexo.mime_type if inline else "application/octet-stream", headers=headers)


@router.post("", response_model=ChamadoResumo, status_code=201)
def criar(dados: NovoChamado, jira: JiraClient = Depends(get_jira)):
    try:
        ticket = jira.create_ticket(dados.summary.strip(), dados.area)
    except JiraError as exc:
        raise _erro_jira(exc) from exc
    invalidar_cache()
    return ticket
