import { useState } from 'react'
import { Link } from 'react-router-dom'
import { criarChamado, mensagemErro } from '../api.js'
import { Aviso, Icone } from '../ui.jsx'

const AREAS = [
  { valor: 'RH', icone: 'rh' },
  { valor: 'Operations', icone: 'operations' },
  { valor: 'Comercial', icone: 'comercial' },
]
const LIMITE = 255
const MINIMO = 10

const PASSOS = [
  { n: 1, classe: 'p1', titulo: 'A IA lê o pedido', texto: ' e confere se os dados estão claros, completos e seguros.' },
  { n: 2, classe: 'p2', titulo: 'Se estiver tudo certo,', texto: ' o robô executa e devolve o resultado.' },
  { n: 3, classe: 'p3', titulo: 'Se houver dúvida,', texto: ' um atendente assume, já com o resumo e o motivo.' },
]

export default function Criar() {
  const [area, setArea] = useState('')
  const [texto, setTexto] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState(null)
  const [criado, setCriado] = useState(null)

  const pronto = area !== '' && texto.trim().length >= MINIMO

  async function enviar(e) {
    e.preventDefault()
    if (!pronto) return
    setEnviando(true)
    setErro(null)
    setCriado(null)
    try {
      setCriado(await criarChamado({ summary: texto.trim(), area }))
      setTexto('')
      setArea('')
    } catch (err) {
      setErro(mensagemErro(err))
    } finally {
      setEnviando(false)
    }
  }

  let dica = 'Você pode acompanhar o andamento depois de criar.'
  if (!area) dica = 'Escolha a área solicitante.'
  else if (texto.trim().length < MINIMO) dica = 'Escreva pelo menos uma frase para liberar o botão.'

  return (
    <>
      <div className="titulo">
        <h1>Novo chamado</h1>
        <p>Conte o que você precisa com as suas palavras. Se estiver tudo claro, o robô resolve. Se não, uma pessoa da equipe assume.</p>
      </div>

      <div className="duas-colunas">
        <form className="painel form" onSubmit={enviar}>
          <fieldset>
            <legend>Área solicitante</legend>
            <div className="areas">
              {AREAS.map((a) => (
                <button
                  type="button"
                  key={a.valor}
                  className={`area ${area === a.valor ? 'ativa' : ''}`}
                  aria-pressed={area === a.valor}
                  onClick={() => setArea(a.valor)}
                >
                  <Icone nome={a.icone} tamanho={22} traco={1.5} />
                  <span>{a.valor}</span>
                </button>
              ))}
            </div>
          </fieldset>

          <div className="campo">
            <label htmlFor="resumo">Resumo do pedido</label>
            <textarea
              id="resumo"
              rows={6}
              maxLength={LIMITE}
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
              placeholder="Ex.: Calcule 1250 dividido por 5 na calculadora."
            />
            <div className="campo-rodape">
              <span>Quanto mais claro o pedido, maior a chance de o robô resolver sozinho.</span>
              <span className="num">{texto.length} / {LIMITE}</span>
            </div>
          </div>

          <div className="acoes">
            <button type="submit" className="primario" disabled={!pronto || enviando}>
              {enviando ? 'Enviando…' : 'Criar chamado'}
            </button>
            <span className="dica">{dica}</span>
          </div>

          {erro && <Aviso>{erro}</Aviso>}
          {criado && (
            <Aviso tipo="ok">
              <div>
                <strong>Chamado {criado.key} criado</strong>
                <span>A IA já está lendo o pedido. Você acompanha tudo na aba Acompanhamento.</span>
              </div>
              <Link to="/acompanhar" className="botao-claro">Ver acompanhamento</Link>
            </Aviso>
          )}
        </form>

        <aside className="depois">
          <h2>O que acontece depois</h2>
          <ol>
            {PASSOS.map((p) => (
              <li key={p.n} className="painel passo">
                <span className={`bolinha ${p.classe}`}>{p.n}</span>
                <span><strong>{p.titulo}</strong>{p.texto}</span>
              </li>
            ))}
          </ol>
        </aside>
      </div>
    </>
  )
}
