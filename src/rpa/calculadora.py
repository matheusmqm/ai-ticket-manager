import logging
import re
import subprocess
from decimal import Decimal, DivisionByZero, InvalidOperation
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pywinauto import Desktop
from pywinauto.base_wrapper import BaseWrapper

from src.rpa.models import RpaResult

log = logging.getLogger("rpa.calculadora")

JANELA = {"class_name": "ApplicationFrameWindow", "title_re": "Calculadora|Calculator"}
OPERACOES = {"+": "plusButton", "-": "minusButton", "*": "multiplyButton", "/": "divideButton"}
SIMBOLOS = {"+": "+", "-": "-", "*": "x", "/": "÷"}


class CalculoForm(BaseModel):
    a: str = Field(pattern=r"^-?\d+([.,]\d+)?$")
    b: str = Field(pattern=r"^-?\d+([.,]\d+)?$")
    operacao: Literal["+", "-", "*", "/"]


def _decimal(texto: str) -> Decimal:
    return Decimal(texto.replace(",", "."))


def _botao(janela: BaseWrapper, auto_id: str) -> BaseWrapper:
    return janela.child_window(auto_id=auto_id, control_type="Button")


def _clicar(janela: BaseWrapper, auto_id: str) -> None:
    _botao(janela, auto_id).invoke()


def _digitar(janela: BaseWrapper, numero: str) -> None:
    """Digita o número clicando botão a botão (sem depender de foco/teclado)."""
    negativo = numero.startswith("-")
    for ch in numero.lstrip("-"):
        _clicar(janela, "decimalSeparatorButton" if ch in ",." else f"num{ch}Button")
    if negativo:
        _clicar(janela, "negateButton")


def _ler_visor(janela: BaseWrapper) -> str:
    """Texto do visor, ex.: 'A exibição é 10' -> '10'."""
    texto = janela.child_window(auto_id="CalculatorResults").window_text()
    return re.sub(r"^\D*?(?=-?[\d])", "", texto).replace("‎", "").strip()


def _numero_do_visor(visor: str) -> Decimal:
    # remove separador de milhar (ponto/espaço) e usa a vírgula como decimal (pt-BR)
    limpo = re.sub(r"[\s. ]", "", visor).replace(",", ".")
    return Decimal(limpo)


def _abrir() -> BaseWrapper:
    # No Windows 11 o calc.exe é só um lançador: o app real roda em outro processo,
    # então localizamos a janela pela classe/título em vez de usar o Application.
    subprocess.Popen(["calc.exe"])
    janela = Desktop(backend="uia").window(**JANELA)
    janela.wait("visible", timeout=20)
    janela.set_focus()
    return janela


def _fechar(janela: BaseWrapper | None) -> None:
    if janela is None:
        return
    try:
        janela.close()
    except Exception as exc:  # fechar é melhor esforço
        log.warning("não foi possível fechar a Calculadora: %s", exc)


def _print(janela: BaseWrapper, caminho: Path) -> str:
    janela.set_focus()
    janela.capture_as_image().save(caminho)
    return str(caminho)


def calcular(
    dados: CalculoForm,
    ticket: str = "-",
    evidencias_dir: str | Path = "evidencias",
) -> RpaResult:
    """Faz a conta na Calculadora, confere o resultado em código e tira o print."""
    pasta = Path(evidencias_dir) / ticket
    pasta.mkdir(parents=True, exist_ok=True)
    evidencias: list[str] = []
    janela: BaseWrapper | None = None
    expressao = f"{dados.a} {dados.operacao} {dados.b}"

    try:
        log.info("[%s] abrindo Calculadora: %s", ticket, expressao)
        janela = _abrir()
        _clicar(janela, "clearButton")

        _digitar(janela, dados.a)
        _clicar(janela, OPERACOES[dados.operacao])
        _digitar(janela, dados.b)
        _clicar(janela, "equalButton")

        visor = _ler_visor(janela)
        log.info("[%s] visor: %s", ticket, visor)
        evidencias.append(_print(janela, pasta / "calculadora.png"))

        # validação determinística: o código confere o que o robô leu na tela
        a, b = _decimal(dados.a), _decimal(dados.b)
        try:
            esperado = {"+": a + b, "-": a - b, "*": a * b, "/": a / b}[dados.operacao]
        except (DivisionByZero, InvalidOperation):
            raise ValueError(f"operação inválida ({expressao}); visor: '{visor}'") from None
        try:
            obtido = _numero_do_visor(visor)
        except InvalidOperation:
            raise ValueError(f"visor sem número ('{visor}') para {expressao}") from None
        # o visor arredonda divisões longas: compara com a precisão exibida
        casas = max(-obtido.as_tuple().exponent, 0)
        if round(esperado, casas) != obtido:
            raise ValueError(f"resultado divergente: esperado {esperado}, visor '{visor}'")

        msg = f"{dados.a} {SIMBOLOS[dados.operacao]} {dados.b} = {visor} (conferido)"
        log.info("[%s] %s", ticket, msg)
        return RpaResult(success=True, message=msg, evidencias=evidencias)
    except Exception as exc:  # falha de robô nunca derruba o orquestrador
        log.error("[%s] falha na Calculadora: %s", ticket, exc)
        if janela is not None:
            try:
                evidencias.append(_print(janela, pasta / "erro.png"))
            except Exception as shot_exc:
                log.warning("[%s] sem screenshot de erro: %s", ticket, shot_exc)
        return RpaResult(success=False, message=f"Falha na Calculadora: {exc}", evidencias=evidencias)
    finally:
        _fechar(janela)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    print(calcular(CalculoForm(a="7", b="3", operacao="+"), ticket="demo").model_dump_json(indent=2))
