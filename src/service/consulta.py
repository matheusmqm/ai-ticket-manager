"""Consulta de pedidos: lê a planilha pública do Google (CSV) com DuckDB e roda um SELECT.

Dois modos: lista de pedidos (SELECT colunas ... WHERE) ou agregação (soma, contagem, média,
máximo, mínimo, com GROUP BY opcional), que devolve só o resultado.

Os nomes de coluna vêm do cabeçalho da planilha e só entram no SQL se estiverem em COLUNAS_PEDIDOS
(lista fixa); operadores e operações também vêm de listas fixas; os valores dos filtros vão sempre
como parâmetros (?), nunca concatenados.
"""

import logging
import tempfile
from pathlib import Path

import duckdb
import httpx

from src.config import get_settings
from src.models.rpa import RpaResult
from src.service.regras import (
    COLUNAS_AGRUPAMENTO,
    COLUNAS_NUMERICAS,
    COLUNAS_PEDIDOS,
    OPERACOES_AGREGACAO,
    OPERADORES_FILTRO,
    normalizar_coluna,
)

log = logging.getLogger("consulta")

_FUNCAO_SQL = {"soma": "SUM", "contagem": "COUNT", "media": "AVG", "maximo": "MAX", "minimo": "MIN"}
_ROTULO = {"soma": "soma", "contagem": "contagem", "media": "média", "maximo": "máximo", "minimo": "mínimo"}

# (coluna, operador, valor)
FiltroConsulta = tuple[str, str, str]
# (operação, coluna ou None)
AgregacaoConsulta = tuple[str, str | None]


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


def _numero(coluna: str) -> str:
    """Coluna numérica como DOUBLE, aceitando vírgula decimal ('18750,50') caso o CSV a traga como texto."""
    return f"TRY_CAST(REPLACE(CAST({coluna} AS VARCHAR), ',', '.') AS DOUBLE)"


def montar_sql(
    colunas: list[str],
    filtros: list[FiltroConsulta],
    agregacao: AgregacaoConsulta | None = None,
    agrupar_por: list[str] | None = None,
) -> tuple[str, list[str], list[str]]:
    """Devolve (sql, parâmetros, rótulos das colunas do resultado). Levanta ValueError se algo for inválido."""
    where = [(normalizar_coluna(c), op.strip(), v.strip()) for c, op, v in filtros]
    grupos = [normalizar_coluna(c) for c in agrupar_por or []]
    sel = [normalizar_coluna(c) for c in colunas] or ["cliente", "valor", "qnt_produtos", "empresa"]

    usadas = [*(c for c, _, _ in where), *grupos, *(sel if not agregacao else [])]
    if agregacao and agregacao[1]:
        usadas.append(normalizar_coluna(agregacao[1]))
    if any(c not in COLUNAS_PEDIDOS for c in usadas):
        raise ValueError("coluna inexistente na base de pedidos")
    if any(op not in OPERADORES_FILTRO for _, op, _ in where):
        raise ValueError("operador de filtro inválido")
    if any(g not in COLUNAS_AGRUPAMENTO for g in grupos):
        raise ValueError("agrupamento só por cliente ou empresa")
    if grupos and not agregacao:
        raise ValueError("agrupamento exige agregação")

    condicoes, params = [], []
    for coluna, op, valor in where:
        if coluna in COLUNAS_NUMERICAS:
            condicoes.append(f"{_numero(coluna)} {op} CAST(? AS DOUBLE)")
            params.append(valor.replace(",", "."))
        elif op in {"=", "!="}:
            condicoes.append(f"lower({coluna}) {op} lower(?)")
            params.append(valor)
        else:
            raise ValueError(f"operador '{op}' só vale para colunas numéricas")
    clausula = f" WHERE {' AND '.join(condicoes)}" if condicoes else ""

    if not agregacao:
        return f"SELECT {', '.join(sel)} FROM pedidos{clausula}", params, sel

    operacao, col_agg = agregacao
    if operacao not in OPERACOES_AGREGACAO:
        raise ValueError("operação de agregação inválida")
    if operacao == "contagem":
        expr, rotulo = "COUNT(*)", "pedidos"
    else:
        coluna = normalizar_coluna(col_agg or "")
        if coluna not in COLUNAS_NUMERICAS:
            raise ValueError(f"não dá para calcular {operacao} da coluna '{col_agg}'")
        expr, rotulo = f"{_FUNCAO_SQL[operacao]}({_numero(coluna)})", coluna
    rotulo = f"{_ROTULO[operacao]} de {rotulo}"

    if grupos:
        lista = ", ".join(grupos)
        sql = f"SELECT {lista}, {expr} FROM pedidos{clausula} GROUP BY {lista} ORDER BY {lista}"
        return sql, params, [*grupos, rotulo]
    return f"SELECT {expr} FROM pedidos{clausula}", params, [rotulo]


def _formatar(valor: object) -> str:
    """Número sem '.0' à toa e com no máximo 2 casas; o resto como texto."""
    if isinstance(valor, float):
        return str(int(valor)) if valor.is_integer() else f"{valor:.2f}"
    return str(valor)


def _descrever_filtros(filtros: list[FiltroConsulta]) -> str:
    return ", ".join(f"{normalizar_coluna(c)} {op} {v}" for c, op, v in filtros)


def executar_consulta(
    con: duckdb.DuckDBPyConnection,
    colunas: list[str],
    filtros: list[FiltroConsulta],
    agregacao: AgregacaoConsulta | None = None,
    agrupar_por: list[str] | None = None,
    ticket: str = "-",
) -> RpaResult:
    """Roda a consulta numa conexão que já tem a tabela 'pedidos'."""
    try:
        sql, params, rotulos = montar_sql(colunas, filtros, agregacao, agrupar_por)
    except ValueError as exc:
        return RpaResult(success=False, message=str(exc))
    log.info("[%s] %s %s", ticket, sql, params)

    try:
        linhas = con.execute(sql, params).fetchall()
    except duckdb.Error as exc:
        log.exception("[%s] falha na consulta", ticket)
        return RpaResult(success=False, message=f"falha ao consultar a planilha: {exc}")

    escopo = f" ({_descrever_filtros(filtros)})" if filtros else ""

    if agregacao and not agrupar_por:
        valor = linhas[0][0] if linhas else None
        if valor is None:  # SUM/AVG/MAX/MIN de zero linhas
            return RpaResult(success=False, message="nenhum pedido encontrado com esses filtros")
        return RpaResult(success=True, message=f"{rotulos[0]}{escopo}: {_formatar(valor)}")

    if not linhas:
        return RpaResult(success=False, message="nenhum pedido encontrado com esses filtros")

    if agregacao:
        texto = "\n".join(f"{', '.join(str(x) for x in l[:-1])}: {_formatar(l[-1])}" for l in linhas)
        return RpaResult(success=True, message=f"{rotulos[-1]} por {', '.join(rotulos[:-1])}{escopo}:\n{texto}")

    texto = "\n".join(", ".join(f"{c}={v}" for c, v in zip(rotulos, l)) for l in linhas)
    return RpaResult(success=True, message=f"{len(linhas)} pedido(s) encontrado(s):\n{texto}")


def consultar(
    colunas: list[str],
    filtros: list[FiltroConsulta],
    ticket: str = "-",
    agregacao: AgregacaoConsulta | None = None,
    agrupar_por: list[str] | None = None,
) -> RpaResult:
    """Baixa a planilha e roda a consulta (lista de pedidos ou agregação)."""
    try:
        con = _abrir_planilha(get_settings().planilha_pedidos_url)
    except (httpx.HTTPError, duckdb.Error) as exc:
        log.exception("[%s] falha ao abrir a planilha", ticket)
        return RpaResult(success=False, message=f"falha ao consultar a planilha: {exc}")
    return executar_consulta(con, colunas, filtros, agregacao, agrupar_por, ticket)
