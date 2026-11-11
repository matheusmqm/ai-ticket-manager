"""Cliente da API REST v3 do Jira Cloud (síncrono, httpx)."""

import json
import logging
import time
from pathlib import Path
from typing import Any

import httpx

from src.config import Settings, get_settings
from src.models.ticket import Ticket

log = logging.getLogger("jira")

MAX_RETRIES = 3


class JiraError(Exception):
    """Falha na chamada ao Jira (HTTP, rede ou dado inesperado)."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _adf_paragraphs(text: str) -> list[dict[str, Any]]:
    return [
        {"type": "paragraph", "content": [{"type": "text", "text": line}]} if line else {"type": "paragraph"}
        for line in text.split("\n")
    ]


def _adf_to_text(node: Any) -> str:
    """Extrai texto puro de um documento ADF."""
    if not node:
        return ""
    if isinstance(node, str):
        return node
    if node.get("type") == "text":
        return node.get("text", "")
    parts = [_adf_to_text(child) for child in node.get("content", [])]
    sep = "\n" if node.get("type") in {"doc", "bulletList", "orderedList"} else ""
    return sep.join(parts)


class JiraClient:
    def __init__(self, settings: Settings | None = None, client: httpx.Client | None = None):
        self._s = settings or get_settings()
        self._http = client or httpx.Client(
            base_url=self._s.jira_base_url.rstrip("/"),
            auth=(self._s.jira_email, self._s.jira_api_token.get_secret_value()),
            headers={"Accept": "application/json"},
            timeout=30,
        )
        self._fields: dict[str, str] | None = None

    def close(self) -> None:
        self._http.close()

    # ------------------------------------------------------------------ HTTP

    def _request(self, method: str, path: str, *, ticket: str = "-", **kwargs: Any) -> httpx.Response:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self._http.request(method, path, **kwargs)
            except httpx.HTTPError as exc:
                log.error("[%s] %s %s falhou na rede: %s", ticket, method, path, exc)
                raise JiraError(f"Erro de rede em {method} {path}: {exc}") from exc

            if resp.status_code == 429 and attempt < MAX_RETRIES:
                wait = float(resp.headers.get("Retry-After", 2 * attempt))
                log.warning("[%s] rate limit (429) em %s, aguardando %.0fs", ticket, path, wait)
                time.sleep(wait)
                continue
            if resp.is_success:
                return resp

            detail = resp.text[:500]
            log.error("[%s] %s %s -> %s %s", ticket, method, path, resp.status_code, detail)
            raise JiraError(f"{method} {path} -> {resp.status_code}: {detail}", resp.status_code)
        raise JiraError(f"{method} {path}: tentativas esgotadas")  # pragma: no cover

    # ----------------------------------------------------- campos do projeto

    def field_ids(self) -> dict[str, str]:
        """IDs dos campos personalizados, descobertos pelos metadados (nunca fixos no código)."""
        if self._fields is not None:
            return self._fields
        s = self._s
        overrides = {"area": s.jira_field_area, "categoria": s.jira_field_categoria, "decisao": s.jira_field_decisao}
        names = {"area": "Área Solicitante", "categoria": "Categoria", "decisao": "Decisão"}

        found: dict[str, str] = {}
        if not all(overrides.values()):
            base = f"/rest/api/3/issue/createmeta/{s.jira_project_key}/issuetypes"
            types = self._request("GET", base).json().get("issueTypes", [])
            type_id = next((t["id"] for t in types if t["name"] == s.jira_issue_type), None)
            if type_id is None:
                raise JiraError(f"Tipo de item '{s.jira_issue_type}' não existe no projeto {s.jira_project_key}")
            meta = self._request("GET", f"{base}/{type_id}").json().get("fields", [])
            by_name = {f["name"]: f["fieldId"] for f in meta}
            found = {k: by_name[n] for k, n in names.items() if n in by_name}

        self._fields = {k: overrides[k] or found.get(k, "") for k in names}
        missing = [names[k] for k, v in self._fields.items() if not v]
        if missing:
            log.warning("[-] campos não encontrados no Jira: %s", ", ".join(missing))
        return self._fields

    def _field_list(self) -> str:
        f = self.field_ids()
        extra = [v for v in f.values() if v]
        return ",".join(["summary", "description", "status", "priority", *extra])

    # ---------------------------------------------------------------- leitura

    def _to_ticket(self, issue: dict[str, Any]) -> Ticket:
        f, ids = issue["fields"], self.field_ids()

        def option(key: str) -> str | None:
            v = f.get(ids[key]) if ids[key] else None
            return v.get("value") if isinstance(v, dict) else None

        return Ticket(
            key=issue["key"],
            summary=f.get("summary") or "",
            description=_adf_to_text(f.get("description")),
            status=f["status"]["name"],
            priority=(f.get("priority") or {}).get("name"),
            area=option("area"),
            categoria=option("categoria"),
            decisao=option("decisao"),
        )

    def get_ticket(self, key: str) -> Ticket:
        resp = self._request("GET", f"/rest/api/3/issue/{key}", ticket=key, params={"fields": self._field_list()})
        return self._to_ticket(resp.json())

    def search(self, jql: str, max_results: int = 50) -> list[Ticket]:
        """Busca por JQL em /search/jql (paginação por token, sem total)."""
        tickets: list[Ticket] = []
        token: str | None = None
        while True:
            params: dict[str, Any] = {"jql": jql, "maxResults": max_results, "fields": self._field_list()}
            if token:
                params["nextPageToken"] = token
            data = self._request("GET", "/rest/api/3/search/jql", params=params).json()
            tickets.extend(self._to_ticket(i) for i in data.get("issues", []))
            token = data.get("nextPageToken")
            if data.get("isLast", True) or not token:
                return tickets

    def tickets_in_status(self, status: str) -> list[Ticket]:
        """Chamados de uma fila (status), mais antigos primeiro."""
        jql = f'project = "{self._s.jira_project_key}" AND status = "{status}" ORDER BY created ASC'
        return self.search(jql)

    # --------------------------------------------------------------- escrita

    def create_ticket(
        self, summary: str, area: str, description: str | None = None, priority: str | None = None
    ) -> Ticket:
        ids = self.field_ids()
        fields: dict[str, Any] = {
            "project": {"key": self._s.jira_project_key},
            "issuetype": {"name": self._s.jira_issue_type},
            "summary": summary[:255],
            ids["area"]: {"value": area},
        }
        if description:
            fields["description"] = {"type": "doc", "version": 1, "content": _adf_paragraphs(description)}
        if priority:
            fields["priority"] = {"name": priority}
        key = self._request("POST", "/rest/api/3/issue", json={"fields": fields}).json()["key"]
        log.info("[%s] chamado criado", key)
        return self.get_ticket(key)

    def update_fields(
        self,
        key: str,
        *,
        categoria: str | None = None,
        decisao: str | None = None,
        priority: str | None = None,
    ) -> None:
        ids = self.field_ids()
        fields: dict[str, Any] = {}
        if categoria:
            fields[ids["categoria"]] = {"value": categoria}
        if decisao:
            fields[ids["decisao"]] = {"value": decisao}
        if priority:
            fields["priority"] = {"name": priority}
        if fields:
            self._request("PUT", f"/rest/api/3/issue/{key}", ticket=key, json={"fields": fields})
            log.info("[%s] campos atualizados: %s", key, ", ".join(fields))

    def set_description(self, key: str, text: str) -> None:
        """Escreve a resposta do sistema na Description (substitui o conteúdo anterior)."""
        body = {"fields": {"description": {"type": "doc", "version": 1, "content": _adf_paragraphs(text)}}}
        self._request("PUT", f"/rest/api/3/issue/{key}", ticket=key, json=body)
        log.info("[%s] description atualizada", key)

    def transition_to(self, key: str, status: str) -> None:
        """Move o chamado para um status executando a transição correspondente."""
        resp = self._request("GET", f"/rest/api/3/issue/{key}/transitions", ticket=key)
        match = next((t for t in resp.json()["transitions"] if t["to"]["name"] == status), None)
        if match is None:
            raise JiraError(f"{key}: nenhuma transição disponível para '{status}'")
        self._request("POST", f"/rest/api/3/issue/{key}/transitions", ticket=key, json={"transition": {"id": match["id"]}})
        log.info("[%s] status -> %s", key, status)

    def add_comment(self, key: str, text: str) -> None:
        body = {"body": {"type": "doc", "version": 1, "content": _adf_paragraphs(text)}}
        self._request("POST", f"/rest/api/3/issue/{key}/comment", ticket=key, json=body)
        log.info("[%s] comentário adicionado", key)

    def add_json_comment(self, key: str, data: dict[str, Any], title: str | None = None) -> None:
        """Comentário estruturado: título opcional + bloco de código JSON."""
        content: list[dict[str, Any]] = []
        if title:
            content.append({"type": "paragraph", "content": [{"type": "text", "text": title}]})
        content.append(
            {
                "type": "codeBlock",
                "attrs": {"language": "json"},
                "content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False, indent=2)}],
            }
        )
        body = {"body": {"type": "doc", "version": 1, "content": content}}
        self._request("POST", f"/rest/api/3/issue/{key}/comment", ticket=key, json=body)
        log.info("[%s] comentário JSON adicionado", key)

    def attach(self, key: str, path: str | Path) -> None:
        path = Path(path)
        with path.open("rb") as fh:
            self._request(
                "POST",
                f"/rest/api/3/issue/{key}/attachments",
                ticket=key,
                headers={"X-Atlassian-Token": "no-check"},
                files={"file": (path.name, fh)},
            )
        log.info("[%s] anexo enviado: %s", key, path.name)
