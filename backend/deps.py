"""Dependências compartilhadas: um JiraClient para o processo e um cache curto em memória.

O cache existe só para respeitar o limite de uso do Jira quando várias telas recarregam ao mesmo tempo.
Não é persistência: some quando a API reinicia."""

import threading
import time
from collections.abc import Callable
from typing import Any

from src.service.jira_client import JiraClient

CACHE_SEGUNDOS = 5

_jira: JiraClient | None = None
_cache: dict[str, tuple[float, Any]] = {}
_lock = threading.Lock()


def get_jira() -> JiraClient:
    global _jira
    with _lock:
        if _jira is None:
            _jira = JiraClient()
        return _jira


def fechar_jira() -> None:
    global _jira
    if _jira is not None:
        _jira.close()
        _jira = None


def cacheado(chave: str, carregar: Callable[[], Any]) -> Any:
    agora = time.monotonic()
    with _lock:
        hit = _cache.get(chave)
        if hit and agora - hit[0] < CACHE_SEGUNDOS:
            return hit[1]
    valor = carregar()
    with _lock:
        _cache[chave] = (time.monotonic(), valor)
    return valor


def todos_chamados(jira: JiraClient) -> list:
    """Todos os chamados com histórico de status. Lista e métricas dividem o mesmo cache."""
    return cacheado("todos", lambda: jira.all_tickets(changelog=True))


def invalidar_cache() -> None:
    with _lock:
        _cache.clear()
