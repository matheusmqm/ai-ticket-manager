// Mapeamento dos status do Jira para as etapas mostradas ao cliente (CLAUDE.md) e ícones.

export const ICONES = {
  circle: 'M8 2.5a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11z',
  arc: 'M8 2.5a5.5 5.5 0 1 1-5.5 5.5',
  person: 'M8 8a2.6 2.6 0 1 0 0-5.2A2.6 2.6 0 0 0 8 8zM3 13.5c.4-2.4 2.4-3.8 5-3.8s4.6 1.4 5 3.8',
  check: 'M3.5 8.5l3 3 6-6.5',
  x: 'M4 4l8 8M12 4l-8 8',
  bolt: 'M9 1.5L3.5 9h4l-1 5.5L12.5 7h-4z',
  refresh: 'M13 6.5A5.5 5.5 0 0 0 3.2 5M3 2.5V5h2.5M3 9.5A5.5 5.5 0 0 0 12.8 11M13 13.5V11h-2.5',
  rh: 'M6 7.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5zM1.5 13.5c.3-2.3 2.2-3.7 4.5-3.7s4.2 1.4 4.5 3.7M11 7a2 2 0 1 0 0-4M12 10c1.4.4 2.3 1.5 2.5 3.5',
  operations: 'M13 6.5A5.5 5.5 0 0 0 3.2 5M3 2.5V5h2.5M3 9.5A5.5 5.5 0 0 0 12.8 11M13 13.5V11h-2.5',
  comercial: 'M2.5 13.5V8M8 13.5V4.5M13.5 13.5V2.5',
  none: 'M0 0',
}

// kind = etapa mostrada ao cliente. cor = cor das barras nas métricas.
export const ETAPAS = {
  recebido: { label: 'Recebido', icone: 'circle', cor: '#7C8799' },
  proc: { label: 'Em processamento', icone: 'arc', cor: '#3B6FE0' },
  analise: { label: 'Com atendente', icone: 'person', cor: '#C96F00' },
  ok: { label: 'Concluído', icone: 'check', cor: '#2E9E6A' },
  falha: { label: 'Com falha', icone: 'x', cor: '#C73A34' },
}

const STATUS_PARA_ETAPA = {
  Novo: 'recebido',
  'Fila Automação': 'proc',
  'Em Execução': 'proc',
  'Aguardando Revisão Humana': 'analise',
  Concluído: 'ok',
  Falhou: 'falha',
}

export const etapaDe = (status) => STATUS_PARA_ETAPA[status] ?? 'recebido'

export const DECISOES = {
  Automatizar: { label: 'Automatizar', icone: 'bolt', classe: 'auto' },
  'Decisão Humana': { label: 'Revisão humana', icone: 'person', classe: 'humano' },
}
export const DECISAO_PENDENTE = { label: 'Aguardando', icone: 'circle', classe: 'espera' }

// O Jira devolve "2026-11-12T01:40:00.000-0300"; alguns navegadores exigem "-03:00".
export function formatarData(iso) {
  if (!iso) return '—'
  const d = new Date(iso.replace(/([+-]\d{2})(\d{2})$/, '$1:$2'))
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}
