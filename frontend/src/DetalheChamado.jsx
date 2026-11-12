import { useEffect, useRef, useState } from 'react'
import { mensagemErro, obterChamado, urlAnexo } from './api.js'
import { ETAPAS, ICONES, etapaDe, formatarData } from './status.js'
import { Aviso, DecisaoTag, EtapaTag } from './ui.jsx'

// Estado de cada etapa da linha do tempo: done | current | skipped | todo | fail
function estadosDaLinha(etapa, humano, falhou) {
  if (etapa === 'recebido') return ['current', 'todo', 'todo', 'todo']
  if (etapa === 'proc') return ['done', 'current', 'skipped', 'todo']
  if (etapa === 'analise') return falhou ? ['done', 'fail', 'current', 'todo'] : ['done', 'skipped', 'current', 'todo']
  if (etapa === 'ok') return humano ? ['done', 'skipped', 'done', 'done'] : ['done', 'done', 'skipped', 'done']
  return ['done', 'done', 'skipped', 'fail']
}

const NOMES = ['Recebido', 'Em processamento', 'Análise por atendente', 'Concluído']
const NOTAS = {
  current: ['Entrou na fila.', 'O robô está executando a tarefa.', 'Uma pessoa está avaliando o pedido.'],
  done: ['Pedido registrado.', 'Tarefa executada pelo robô.', 'Avaliado por um atendente.', 'Resultado devolvido.'],
  skipped: [null, 'Pulado: a IA chamou uma pessoa.', 'Não necessária neste pedido.'],
  todo: [null, 'Depende da decisão da IA.', 'Depende da decisão da IA.', 'Ainda não concluído.'],
  fail: [null, 'O robô não conseguiu concluir.', null, 'O robô não conseguiu concluir.'],
}

function LinhaDoTempo({ chamado }) {
  const etapa = etapaDe(chamado.status)
  const estados = estadosDaLinha(etapa, chamado.decisao === 'Decisão Humana', chamado.passou_por_falhou)
  return (
    <ol className="linha-tempo">
      {estados.map((estado, i) => {
        const nome = i === 3 && estado === 'fail' ? 'Concluído com falha' : NOMES[i]
        const icone = { done: 'check', fail: 'x', current: ETAPAS[etapa]?.icone ?? 'circle' }[estado] ?? 'none'
        return (
          <li key={NOMES[i]}>
            <div className="coluna-ponto">
              <span className={`ponto ${estado} ${estado === 'current' ? `etapa-${etapa}` : ''}`}>
                <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true" className="icone" style={{ strokeWidth: 2 }}>
                  <path d={ICONES[icone]} />
                </svg>
              </span>
              {i < 3 && <span className={`fio ${estado === 'done' ? 'feito' : ''}`} />}
            </div>
            <div className="passo-txt">
              <strong className={estado}>{nome}</strong>
              <span>{NOTAS[estado][i] ?? ''}</span>
            </div>
          </li>
        )
      })}
    </ol>
  )
}

function Evidencias({ chamado }) {
  const imagens = chamado.anexos.filter((a) => a.mime_type.startsWith('image/') && !a.mime_type.includes('svg'))
  const outros = chamado.anexos.filter((a) => !imagens.includes(a))
  if (chamado.anexos.length === 0) return <p className="dica">Nenhuma evidência anexada.</p>
  return (
    <>
      <div className="galeria">
        {imagens.map((a) => (
          <a key={a.id} href={urlAnexo(chamado.key, a.id)} target="_blank" rel="noreferrer" className="miniatura">
            <img src={urlAnexo(chamado.key, a.id)} alt={a.filename} loading="lazy" />
            <span>{a.filename}</span>
          </a>
        ))}
      </div>
      {outros.length > 0 && (
        <ul className="anexos">
          {outros.map((a) => (
            <li key={a.id}><a href={urlAnexo(chamado.key, a.id)}>{a.filename}</a></li>
          ))}
        </ul>
      )}
    </>
  )
}

// Janela com todas as informações do chamado. `resumo` é a linha da lista (aparece na hora);
// o resto (descrição, anexos) vem da API.
export default function DetalheChamado({ resumo, aoFechar }) {
  const ref = useRef(null)
  const [detalhe, setDetalhe] = useState(null)
  const [erro, setErro] = useState(null)

  useEffect(() => {
    const dialogo = ref.current
    if (dialogo && !dialogo.open) dialogo.showModal()
  }, [])

  useEffect(() => {
    let ativo = true
    setErro(null)
    obterChamado(resumo.key)
      .then((d) => ativo && setDetalhe(d))
      .catch((err) => ativo && setErro(mensagemErro(err)))
    return () => {
      ativo = false
    }
  }, [resumo.key, resumo.status, resumo.decisao])

  const c = { ...resumo, ...(detalhe?.key === resumo.key ? detalhe : {}) }
  const carregando = !detalhe && !erro

  return (
    <dialog
      ref={ref}
      className="janela"
      aria-labelledby="janela-titulo"
      onClose={aoFechar}
      onClick={(e) => e.target === ref.current && ref.current.close()}
    >
      <div className="janela-corpo">
        <div className="janela-topo">
          <div className="linha-simples">
            <span className="detalhe-id" id="janela-titulo">{c.key}</span>
            <EtapaTag etapa={etapaDe(c.status)} />
          </div>
          <button type="button" className="contorno" onClick={() => ref.current.close()}>Fechar</button>
        </div>
        <h2 className="janela-resumo">{c.summary}</h2>

        {erro && <Aviso>{erro}</Aviso>}

        <div className="janela-grade">
          <div className="janela-esq">
            <dl className="grade-dados">
              <div><dt>Área</dt><dd>{c.area ?? '—'}</dd></div>
              <div><dt>Tipo de automação</dt><dd>{c.categoria ?? 'Ainda não definido'}</dd></div>
              <div><dt>Aberto em</dt><dd>{formatarData(c.created)}</dd></div>
              <div><dt>Prioridade</dt><dd>{c.priority ?? '—'}</dd></div>
            </dl>

            <div className="caixa-ia">
              <div className="linha-simples">
                <span className="rotulo">Decisão da IA</span>
                <DecisaoTag decisao={c.decisao} />
              </div>
              {c.passou_por_falhou && <p className="falha-nota">O robô falhou ao executar este pedido. Um atendente assumiu.</p>}
              <p className="resposta">
                {carregando ? 'Carregando…' : c.description || 'A IA ainda não avaliou este pedido. A decisão aparece aqui em instantes.'}
              </p>
            </div>

            <div className="evidencias">
              <h3 className="rotulo">Evidências</h3>
              {carregando ? <p className="dica">Carregando…</p> : erro ? null : <Evidencias chamado={c} />}
            </div>
          </div>

          <div className="janela-dir">
            <h3 className="rotulo">Linha do tempo</h3>
            <LinhaDoTempo chamado={c} />
          </div>
        </div>
      </div>
    </dialog>
  )
}
