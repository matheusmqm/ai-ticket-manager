import { DECISAO_PENDENTE, DECISOES, ETAPAS, ICONES } from './status.js'

export function Icone({ nome, tamanho = 14, traco = 1.8 }) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 16 16" aria-hidden="true" className="icone" style={{ strokeWidth: traco }}>
      <path d={ICONES[nome]} />
    </svg>
  )
}

export function Logo() {
  return (
    <svg width="36" height="36" viewBox="0 0 48 48" aria-hidden="true">
      <rect width="48" height="48" rx="12" fill="#16305A" />
      <path d="M13 24H25M25 24L35 15M25 24L35 33" fill="none" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="13" cy="24" r="3.5" fill="#fff" />
      <circle cx="37" cy="15" r="3.5" fill="#fff" />
      <circle cx="37" cy="33" r="3.5" fill="#F2A33A" />
    </svg>
  )
}

export function EtapaTag({ etapa }) {
  const e = ETAPAS[etapa]
  return (
    <span className={`tag etapa-${etapa}`}>
      <Icone nome={e.icone} />
      {e.label}
    </span>
  )
}

export function DecisaoTag({ decisao }) {
  const d = DECISOES[decisao] ?? DECISAO_PENDENTE
  return (
    <span className={`decisao ${d.classe}`}>
      <Icone nome={d.icone} traco={1.7} />
      {d.label}
    </span>
  )
}

export function Aviso({ tipo = 'erro', children }) {
  return (
    <div className={`aviso ${tipo}`} role={tipo === 'erro' ? 'alert' : 'status'}>
      {children}
    </div>
  )
}
