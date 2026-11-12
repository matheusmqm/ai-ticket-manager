import { useCallback, useEffect, useState } from 'react'
import { mensagemErro, obterMetricas } from '../api.js'
import { ETAPAS, etapaDe } from '../status.js'
import { Aviso, Icone } from '../ui.jsx'

const INTERVALO_MS = 30000
const ORDEM_ETAPAS = ['recebido', 'proc', 'analise', 'ok']

function Indicador({ titulo, valor, detalhe, icone, cor }) {
  return (
    <div className="painel indicador">
      <span className="indicador-titulo">
        {icone && <span style={{ color: cor, display: 'inline-flex' }}><Icone nome={icone} /></span>}
        {titulo}
      </span>
      <span className="indicador-valor num">{valor}</span>
      <span className="dica">{detalhe}</span>
    </div>
  )
}

// Barras horizontais: itens = [{ rotulo, valor, cor, icone? }]
function Barras({ titulo, itens, nota, vazio = 'Sem dados ainda.' }) {
  const max = Math.max(1, ...itens.map((i) => i.valor))
  return (
    <div className="painel grafico">
      <h2>{titulo}</h2>
      {itens.length === 0 && <p className="dica">{vazio}</p>}
      <div className="barras">
        {itens.map((i) => (
          <div className="barra" key={i.rotulo}>
            <span className="barra-rotulo">
              {i.icone && <span style={{ color: i.cor, display: 'inline-flex' }}><Icone nome={i.icone} traco={2} /></span>}
              {i.rotulo}
            </span>
            <div className="trilho"><div style={{ width: `${(100 * i.valor) / max}%`, background: i.cor, minWidth: i.valor ? 6 : 0 }} /></div>
            <span className="barra-valor num">{i.valor}</span>
          </div>
        ))}
      </div>
      {nota && <p className="dica">{nota}</p>}
    </div>
  )
}

export default function Metricas() {
  const [m, setM] = useState(null)
  const [erro, setErro] = useState(null)

  const carregar = useCallback(async () => {
    try {
      setM(await obterMetricas())
      setErro(null)
    } catch (err) {
      setErro(mensagemErro(err))
    }
  }, [])

  useEffect(() => {
    carregar()
    const id = setInterval(carregar, INTERVALO_MS)
    return () => clearInterval(id)
  }, [carregar])

  // agrupa os status do Jira nas etapas mostradas ao cliente
  const porEtapa = {}
  Object.entries(m?.por_status ?? {}).forEach(([status, n]) => {
    const e = etapaDe(status)
    porEtapa[e] = (porEtapa[e] ?? 0) + n
  })
  const itensEtapa = ORDEM_ETAPAS.map((e) => ({ rotulo: ETAPAS[e].label, valor: porEtapa[e] ?? 0, cor: ETAPAS[e].cor, icone: ETAPAS[e].icone }))
  if (m?.erros.total) itensEtapa.push({ rotulo: ETAPAS.falha.label, valor: m.erros.total, cor: ETAPAS.falha.cor, icone: 'x' })

  const ordenar = (obj, cor) =>
    Object.entries(obj ?? {}).sort((a, b) => b[1] - a[1]).map(([rotulo, valor]) => ({ rotulo, valor, cor }))

  const d = m?.decisao

  return (
    <>
      <div className="titulo linha-titulo">
        <div>
          <h1>Métricas</h1>
          <p>Quanto o robô resolve, quanto vai para a equipe e onde ele falha.</p>
        </div>
        <button type="button" className="contorno" onClick={carregar}>
          <Icone nome="refresh" tamanho={16} />
          Atualizar
        </button>
      </div>

      {erro && <Aviso>{erro}</Aviso>}
      {!m && !erro && <p className="vazio">Carregando…</p>}

      {m && (
        <>
          <section className="indicadores" aria-label="Indicadores">
            <Indicador titulo="Total de chamados" valor={m.total} detalhe={`${m.aguardando_triagem} ainda aguardando decisão da IA`} />
            <Indicador titulo="Automatizados" valor={d.automatizar} detalhe={`${d.pct_automatizar}% dos pedidos já decididos`} icone="bolt" cor="#16305A" />
            <Indicador titulo="Revisão humana" valor={d.humano} detalhe={`${d.pct_humano}% dos pedidos já decididos`} icone="person" cor="#8A4300" />
            <Indicador titulo="Com falha" valor={m.erros.total} detalhe={`${m.erros.pct}% do total de chamados`} icone="x" cor="#A12622" />
          </section>

          <section className="graficos">
            <Barras titulo="Chamados por status" itens={itensEtapa} />

            <div className="painel grafico">
              <h2>Para onde a IA mandou os pedidos</h2>
              {m.triados === 0 ? (
                <p className="dica">Nenhum chamado avaliado ainda.</p>
              ) : (
                <>
                  <div className="divisao" role="img" aria-label={`${d.automatizar} automatizados e ${d.humano} enviados para revisão humana`}>
                    <div style={{ flex: `${d.automatizar} 1 0`, background: '#16305A' }} />
                    <div style={{ flex: `${d.humano} 1 0`, background: '#C96F00' }} />
                  </div>
                  <div className="legenda">
                    <div><i style={{ background: '#16305A' }} /><span>Automatizar</span><strong className="num">{d.automatizar} · {d.pct_automatizar}%</strong></div>
                    <div><i style={{ background: '#C96F00' }} /><span>Revisão humana</span><strong className="num">{d.humano} · {d.pct_humano}%</strong></div>
                  </div>
                  <p className="dica">Considera os {m.triados} chamados já avaliados. Os outros {m.aguardando_triagem} ainda estão na fila de leitura.</p>
                </>
              )}
            </div>

            <Barras titulo="Tipos de automação" itens={ordenar(m.por_automacao, '#16305A')} />
            <Barras
              titulo="Falhas por tipo de automação"
              itens={ordenar(m.erros.por_automacao, '#C73A34')}
              vazio="Nenhuma falha registrada."
            />
          </section>
        </>
      )}
    </>
  )
}
