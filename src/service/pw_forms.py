import logging
import re
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, expect, sync_playwright

from src.models.rpa import PedidoForm, RpaResult

log = logging.getLogger("rpa.forms")

FORM_URL = (
    "https://docs.google.com/forms/d/e/"
    "1FAIpQLSfk6zhNGGS0SwxmqqMGu6QF9chqgv6d8gUG1zSf0aXat7xvWA/viewform"
)
CONFIRMACAO = re.compile(r"Sua resposta foi registrada")

# Rótulos das perguntas, num lugar só. A busca é pelo início do nome acessível.
P_CLIENTE = "Quem é o cliente?"
P_VALOR = "Qual o valor do pedido?"
P_QTD = "Quantos produtos tem o pedido?"


def _textbox(page: Page, pergunta: str):
    return page.get_by_role("textbox", name=re.compile(rf"^{re.escape(pergunta)}"))


def _preencher(page: Page, dados: PedidoForm) -> None:
    _textbox(page, P_CLIENTE).fill(dados.cliente)
    _textbox(page, P_VALOR).fill(dados.valor_pedido)
    _textbox(page, P_QTD).fill(dados.qtd_produtos)
    page.get_by_role("radio", name=dados.empresa, exact=True).check()


def _shot(page: Page, pasta: Path, nome: str, evidencias: list[str]) -> None:
    caminho = pasta / nome
    try:
        page.screenshot(path=str(caminho), full_page=True)
        evidencias.append(str(caminho))
    except PlaywrightError as exc:  # evidência nunca pode causar nova falha
        log.warning("não foi possível salvar %s: %s", nome, exc)


def preencher_formulario(
    dados: PedidoForm,
    ticket: str = "-",
    evidencias_dir: str | Path = "evidencias",
    headless: bool = False,
    slow_mo_ms: int = 500,
    timeout_ms: int = 15_000,
) -> RpaResult:
    """Preenche o formulário, envia e confirma o registro da resposta."""
    pasta = Path(evidencias_dir) / ticket
    pasta.mkdir(parents=True, exist_ok=True)
    evidencias: list[str] = []

    try:
        with sync_playwright() as pw:
            # slow_mo atrasa cada ação para dar tempo de ver os cliques na tela
            browser = pw.chromium.launch(headless=headless, slow_mo=slow_mo_ms)
            # locale fixo: o texto dos botões ("Enviar") depende do idioma do navegador
            context = browser.new_context(locale="pt-BR")
            context.set_default_timeout(timeout_ms)
            context.tracing.start(screenshots=True, snapshots=True)
            page = context.new_page()
            try:
                log.info("[%s] abrindo formulário", ticket)
                page.goto(FORM_URL)
                _preencher(page, dados)
                _shot(page, pasta, "1_preenchido.png", evidencias)

                page.get_by_role("button", name="Enviar", exact=True).click()
                try:
                    expect(page.get_by_text(CONFIRMACAO)).to_be_visible()
                except AssertionError:
                    # sem confirmação: provavelmente erro de validação do próprio formulário
                    erros = [t for t in page.get_by_role("alert").all_inner_texts() if t.strip()]
                    raise PlaywrightError(
                        "envio não confirmado" + (f"; erros do formulário: {erros}" if erros else "")
                    ) from None

                _shot(page, pasta, "2_confirmacao.png", evidencias)
                log.info("[%s] formulário enviado e confirmado", ticket)
                return RpaResult(success=True, message="Resposta registrada no formulário", evidencias=evidencias)
            except Exception:
                _shot(page, pasta, "erro.png", evidencias)
                trace = pasta / "trace.zip"
                try:
                    context.tracing.stop(path=str(trace))
                    evidencias.append(str(trace))
                except PlaywrightError:
                    pass
                raise
            finally:
                context.close()
                browser.close()
    except Exception as exc:  # falha de robô nunca derruba o orquestrador
        log.error("[%s] falha no RPA do formulário: %s", ticket, exc)
        return RpaResult(success=False, message=f"Falha no formulário: {exc}", evidencias=evidencias)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    resultado = preencher_formulario(
        PedidoForm(cliente="Jonas", valor_pedido="143240", qtd_produtos="150", empresa="ENG"),
        ticket="demo",
        headless=False,
    )
    print(resultado.model_dump_json(indent=2))
