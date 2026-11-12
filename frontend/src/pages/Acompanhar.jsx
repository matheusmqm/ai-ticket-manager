import { useCallback, useEffect, useMemo, useState } from 'react'
import { listarChamados, mensagemErro } from '../api.js'
import DetalheChamado from '../DetalheChamado.jsx'
import { ETAPAS, etapaDe } from '../status.js'
import { Aviso, DecisaoTag, EtapaTag, Icone } from '../ui.jsx'

const INTERVALO_MS = 10000
const FILTROS = ['todos', 'recebido', 'proc', 'analise', 'ok', 'falha']
const rotuloFiltro = (f) => (f === 'todos' ? 'Todos' : ETAPAS[f].label)

export default function Acompanhar() {
  const [chamados, setChamados] = useState(null)
  const [erro, setErro] = useState(null)
  const [filtro, setFiltro] = useState('todos')
  const [atualizadoEm, setAtualizadoEm] = useState(null)
  const [aberto, setAberto] = useState(null)

  const carregar = useCallback(async () => {
    try {
      setChamados(await listarChamados())
      setAtualizadoEm(new Date())
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

  const contagem = useMemo(() => {
    const c = { todos: chamados?.length ?? 0 }
    FILTROS.slice(1).forEach((f) => {
      c[f] = (chamados ?? []).filter((x) => (f === 'falha' ? x.passou_por_falhou : etapaDe(x.status) === f)).length
    })
    return c
  }, [chamados])

  const abertoLinha = chamados?.find((c) => c.key === aberto)

  const visiveis = (chamados ?? []).filter((c) => {
    if (filtro === 'todos') return true
    if (filtro === 'falha') return c.passou_por_falhou
    return etapaDe(c.status) === filtro
  })

  return (
    <>
      <div className="titulo linha-titulo">
        <div>
          <h1>Acompanhamento</h1>
          <p>Veja em que etapa está cada pedido e quem está cuidando dele.</p>
        </div>
        <div className="linha-simples">
          <span className="dica">
            {atualizadoEm ? `Atualizado às ${atualizadoEm.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}` : ''}
          </span>
          <button type="button" className="contorno" onClick={carregar}>
            <Icone nome="refresh" tamanho={16} />
            Atualizar
          </button>
        </div>
      </div>

      {erro && <Aviso>{erro}</Aviso>}

      <div className="filtros" role="group" aria-label="Filtrar por status">
        {FILTROS.map((f) => (
          <button key={f} type="button" className={`filtro ${filtro === f ? 'ativo' : ''}`} aria-pressed={filtro === f} onClick={() => setFiltro(f)}>
            {rotuloFiltro(f)}
            <span className="num">{contagem[f]}</span>
          </button>
        ))}
      </div>

      <div className="painel tabela-caixa">
        {!chamados && !erro && <p className="vazio">Carregando…</p>}
        {chamados && visiveis.length === 0 && <p className="vazio">Nenhum chamado neste filtro.</p>}
        {visiveis.length > 0 && (
          <div className="tabela">
            <div className="tr cab">
              <span>Chamado</span><span>Pedido</span><span>Área</span><span>Status</span><span>Automação</span><span>Decisão da IA</span>
            </div>
            {visiveis.map((c) => (
              <button type="button" key={c.key} className="tr linha" onClick={() => setAberto(c.key)} aria-label={`Abrir ${c.key}`}>
                <span className="id">{c.key}</span>
                <span>{c.summary}</span>
                <span className="suave">{c.area ?? '—'}</span>
                <EtapaTag etapa={etapaDe(c.status)} />
                <span className="suave">{c.categoria ?? '—'}</span>
                <DecisaoTag decisao={c.decisao} />
              </button>
            ))}
          </div>
        )}
      </div>

      {abertoLinha && <DetalheChamado resumo={abertoLinha} aoFechar={() => setAberto(null)} />}
    </>
  )
}
