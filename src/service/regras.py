"""Regras determinísticas do agente. O modelo propõe; este código decide.

Cada atividade tem um validador de detalhes que devolve a lista de erros (vazia = ok).
Funções puras: sem rede, sem LLM, fáceis de testar.
"""

from decimal import Decimal

from pydantic import ValidationError

from src.models.agente import Atividade, DadosCalculadora, DadosConsulta, DadosFormulario, Proposta
from src.models.rpa import EMPRESAS, CalculoForm, PedidoForm
from src.models.ticket import Ticket

# Colunas da planilha de pedidos (Google Sheets, respostas do formulário).
COLUNAS_PEDIDOS = frozenset({"timestamp", "cliente", "valor", "qnt_produtos", "empresa"})


def _vazio(valor: str | None) -> bool:
    return valor is None or not valor.strip()


def _erros_pydantic(exc: ValidationError) -> list[str]:
    return [f"valor inválido em '{e['loc'][0]}': {e.get('input')!r}" for e in exc.errors()]


def validar_calculadora(dados: DadosCalculadora) -> list[str]:
    ausentes = []
    if _vazio(dados.a):
        ausentes.append("primeiro número")
    if _vazio(dados.b):
        ausentes.append("segundo número")
    if _vazio(dados.operacao):
        ausentes.append("operação (+, -, *, /)")
    if ausentes:
        return [f"dado ausente no chamado: {', '.join(ausentes)}"]

    try:
        conta = CalculoForm(a=dados.a.strip(), b=dados.b.strip(), operacao=dados.operacao.strip())  # type: ignore[union-attr, arg-type]
    except ValidationError as exc:
        return _erros_pydantic(exc)
    if conta.operacao == "/" and Decimal(conta.b.replace(",", ".")) == 0:
        return ["divisão por zero"]
    return []


def validar_formulario(dados: DadosFormulario) -> list[str]:
    campos = {
        "cliente": dados.cliente,
        "valor_pedido": dados.valor_pedido,
        "qtd_produtos": dados.qtd_produtos,
        "empresa": dados.empresa,
    }
    ausentes = [nome for nome, valor in campos.items() if _vazio(valor)]
    if ausentes:
        # Sem todos os campos o formulário não pode ser preenchido (todos são obrigatórios).
        return [f"campos obrigatórios ausentes no chamado: {', '.join(ausentes)}"]

    try:
        PedidoForm(**{nome: valor.strip() for nome, valor in campos.items()})  # type: ignore[union-attr]
    except ValidationError as exc:
        erros = _erros_pydantic(exc)
        if any("'empresa'" in e for e in erros):
            erros.append(f"empresa deve ser uma de: {', '.join(EMPRESAS)}")
        return erros
    return []


def normalizar_coluna(nome: str) -> str:
    return nome.strip().lower().replace(" ", "_")


def validar_consulta(dados: DadosConsulta) -> list[str]:
    erros = []
    usadas = [*dados.colunas, *(f.coluna for f in dados.filtros)]
    inexistentes = sorted({c for c in usadas if normalizar_coluna(c) not in COLUNAS_PEDIDOS})
    if inexistentes:
        erros.append(
            f"coluna(s) inexistente(s) na base: {', '.join(inexistentes)} "
            f"(colunas válidas: {', '.join(sorted(COLUNAS_PEDIDOS))})"
        )
    if not dados.filtros:
        erros.append("consulta sem filtro: o chamado não diz qual pedido consultar")
    elif any(_vazio(f.valor) for f in dados.filtros):
        erros.append("filtro sem valor")
    return erros


def validar_dados(atividade: Atividade, dados: dict) -> list[str]:
    """Roteia para o validador da atividade. Devolve a lista de erros de dados."""
    try:
        if atividade is Atividade.CALCULADORA:
            return validar_calculadora(DadosCalculadora(**dados))
        if atividade is Atividade.FORMULARIO:
            return validar_formulario(DadosFormulario(**dados))
        if atividade is Atividade.CONSULTA:
            return validar_consulta(DadosConsulta(**dados))
    except (ValidationError, TypeError) as exc:
        return [f"dados extraídos em formato inesperado: {exc}"]
    return []


def validar_alertas(ticket: Ticket, proposta: Proposta) -> list[str]:
    """Regras que mandam o chamado ao humano sem serem falha de dado (regras 2 e 3 do CLAUDE.md)."""
    alertas = []
    # o próprio ID do chamado não conta como referência a outro chamado
    outros = {r.strip().upper() for r in proposta.referencias_chamados if r.strip()} - {ticket.key.upper()}
    if len(outros) > 1:
        alertas.append(
            f"referências a mais de um chamado ({', '.join(sorted(outros))}): possível inconsistência, "
            "nenhum chamado deve ser atualizado"
        )
    elif outros:
        alertas.append(f"o texto cita outro chamado ({', '.join(outros)}) diferente do próprio ({ticket.key})")
    if proposta.acao_ampla:
        alertas.append("ação ampla ou sensível: exige validação humana")
    return alertas
