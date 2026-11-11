"""Registro local das análises (uma linha JSON por análise), para avaliação e monitoramento.

Também serve de memória do worker: o chamado que está em "Fila Automação" é executado com
a mesma análise que o aprovou, sem chamar o LLM de novo.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from src.agent.schema import Analise

log = logging.getLogger("registro")

ARQUIVO = Path("evidencias") / "analises.jsonl"


def salvar_analise(analise: Analise, arquivo: Path = ARQUIVO) -> None:
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    linha = {"quando": datetime.now().isoformat(timespec="seconds"), "analise": analise.model_dump(mode="json")}
    with arquivo.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(linha, ensure_ascii=False) + "\n")
    log.info("[%s] análise registrada", analise.numero_chamado)


def buscar_analise(chamado: str, arquivo: Path = ARQUIVO) -> Analise | None:
    """Última análise registrada do chamado, ou None."""
    if not arquivo.exists():
        return None
    for linha in reversed(arquivo.read_text(encoding="utf-8").splitlines()):
        try:
            dados = json.loads(linha)["analise"]
            if dados["numero_chamado"] == chamado:
                return Analise.model_validate(dados)
        except (ValueError, KeyError):
            log.warning("[%s] linha inválida no registro, ignorada", chamado)
    return None
