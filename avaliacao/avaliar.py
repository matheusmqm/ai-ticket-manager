"""Roda o agente sobre o conjunto de avaliação, imprime acertos/erros e calcula o limiar de confiança.

Uso (na raiz do projeto):
    uv run python -m avaliacao.avaliar              # 3 repetições por caso
    uv run python -m avaliacao.avaliar --rodadas 5

O limiar só pode transformar "automatizar" em "humano". Então o erro que ele precisa evitar é a
AUTOMAÇÃO INDEVIDA: caso esperado "humano" que o agente (já com as regras de código) mandou automatizar.
Regra: o menor limiar, da grade abaixo, que deixa zero automações indevidas; entre os que empatam,
o que mais preserva as automações corretas.
"""

import argparse
import json
import logging
from pathlib import Path

from avaliacao.casos import CASOS
from src.agent.agente import analisar
from src.tickets.models import Ticket

GRADE = [round(0.50 + 0.05 * i, 2) for i in range(11)]  # 0.50 .. 1.00
SAIDA = Path(__file__).parent / "resultados.json"


def rodar(rodadas: int) -> list[dict]:
    registros = []
    for caso in CASOS:
        for r in range(rodadas):
            ticket = Ticket(key="AV-1", summary=caso.texto, status="Novo", area=caso.area)
            a = analisar(ticket)
            registros.append(
                {
                    "caso": caso.id,
                    "rodada": r + 1,
                    "esperado": caso.esperado,
                    "decisao": a.decisao,
                    "confianca": a.confianca,
                    "falha_agente": a.falha and not a.erros,
                    "erros": a.erros,
                    "alertas": a.alertas,
                    "atividade": a.atividade.value,
                }
            )
    return registros


def imprimir(registros: list[dict]) -> None:
    print("\n=== Acertos e erros (decisão final do agente + regras, sem limiar) ===")
    certos = sum(r["decisao"] == r["esperado"] for r in registros)
    print(f"{certos}/{len(registros)} corretos\n")
    for r in registros:
        if r["decisao"] != r["esperado"]:
            print(f"ERRO {r['caso']} r{r['rodada']}: esperado={r['esperado']} obtido={r['decisao']} "
                  f"conf={r['confianca']:.2f} {r['erros'] or r['alertas']}")

    auto = [r for r in registros if r["decisao"] == "automatizar"]
    boas = sorted(r["confianca"] for r in auto if r["esperado"] == "automatizar")
    ruins = sorted(r["confianca"] for r in auto if r["esperado"] == "humano")
    print(f"\nAutomações corretas ({len(boas)}): confianças = {boas}")
    print(f"Automações indevidas ({len(ruins)}): confianças = {ruins}")

    total_boas = sum(r["esperado"] == "automatizar" for r in registros)
    print("\n=== Grade de limiares ===")
    print("limiar | automações indevidas | automações corretas mantidas")
    for t in GRADE:
        indevidas = sum(c >= t for c in ruins)
        mantidas = sum(c >= t for c in boas)
        print(f"{t:>6.2f} | {indevidas:>20} | {mantidas:>3}/{total_boas}")


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    ap = argparse.ArgumentParser()
    ap.add_argument("--rodadas", type=int, default=3)
    ap.add_argument("--reusar", action="store_true", help="não chama a API, relê resultados.json")
    args = ap.parse_args()

    if args.reusar:
        registros = json.loads(SAIDA.read_text(encoding="utf-8"))
    else:
        registros = rodar(args.rodadas)
        SAIDA.write_text(json.dumps(registros, ensure_ascii=False, indent=1), encoding="utf-8")
    imprimir(registros)


if __name__ == "__main__":
    main()
