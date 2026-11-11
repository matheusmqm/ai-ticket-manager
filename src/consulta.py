"""Consulta de pedidos: lê a planilha pública do Google (CSV) com DuckDB e roda um SELECT.

Os nomes de coluna vêm do cabeçalho da planilha e só entram no SQL se estiverem em COLUNAS_PEDIDOS
(lista fixa); os valores dos filtros vão sempre como parâmetros (?), nunca concatenados.
"""

import logging
import tempfile
from pathlib import Path

import duckdb
import httpx

from src.config import get_settings
from src.rpa.models import RpaResult
from src.validation.regras import COLUNAS_PEDIDOS, normalizar_coluna

log = logging.getLogger("consulta")

NUMERICAS = {"valor", "qnt_produtos"}


def _abrir_planilha(url: str) -> duckdb.DuckDBPyConnection:
    """Baixa o CSV e carrega na tabela 'pedidos' (tipos inferidos pelo DuckDB)."""
    resp = httpx.get(url, follow_redirects=True, timeout=20)
    resp.raise_for_status()
    con = duckdb.connect()
    with tempfile.TemporaryDirectory() as pasta:  # read_csv precisa de um arquivo (buffer exige fsspec)
        arquivo = Path(pasta) / "pedidos.csv"
        arquivo.write_bytes(resp.content)
        con.execute("CREATE TABLE pedidos AS SELECT * FROM read_csv(?)", [str(arquivo)])
    return con


def consultar(colunas: list[str], filtros: list[tuple[str, str]], ticket: str = "-") -> RpaResult:
    """SELECT <colunas> FROM pedidos WHERE col = ? AND ... (colunas vazias = todas)."""
    try:
        sel = [normalizar_coluna(c) for c in colunas] or ["cliente", "valor", "qnt_produtos", "empresa"]
        where = [(normalizar_coluna(c), v.strip()) for c, v in filtros]
        if any(c not in COLUNAS_PEDIDOS for c in [*sel, *(c for c, _ in where)]):
            return RpaResult(success=False, message="coluna inexistente na base de pedidos")

        sql = f"SELECT {', '.join(sel)} FROM pedidos"
        params = []
        if where:
            sql += " WHERE " + " AND ".join(
                f"CAST({c} AS DOUBLE) = CAST(? AS DOUBLE)" if c in NUMERICAS else f"lower({c}) = lower(?)"
                for c, _ in where
            )
            params = [v.replace(",", ".") if c in NUMERICAS else v for c, v in where]
        log.info("[%s] %s %s", ticket, sql, params)

        con = _abrir_planilha(get_settings().planilha_pedidos_url)
        linhas = con.execute(sql, params).fetchall()
    except (httpx.HTTPError, duckdb.Error) as exc:
        log.exception("[%s] falha na consulta", ticket)
        return RpaResult(success=False, message=f"falha ao consultar a planilha: {exc}")

    if not linhas:
        return RpaResult(success=False, message="nenhum pedido encontrado com esses filtros")
    texto = "\n".join(", ".join(f"{c}={v}" for c, v in zip(sel, l)) for l in linhas)
    return RpaResult(success=True, message=f"{len(linhas)} pedido(s) encontrado(s):\n{texto}")
