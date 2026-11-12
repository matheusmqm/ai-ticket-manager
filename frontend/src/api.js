import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({ baseURL: BASE_URL, timeout: 30000 })

// Os anexos ficam atrás do login do Jira: a API entrega a imagem para a tela.
export const urlAnexo = (key, id) => `${BASE_URL}/chamados/${key}/anexos/${id}`

export const listarChamados = () => api.get('/chamados').then((r) => r.data)
export const obterChamado = (key) => api.get(`/chamados/${key}`).then((r) => r.data)
export const criarChamado = (dados) => api.post('/chamados', dados).then((r) => r.data)
export const obterMetricas = () => api.get('/metricas').then((r) => r.data)

// Mensagem legível para qualquer erro de chamada à API.
export function mensagemErro(err) {
  const detalhe = err?.response?.data?.detail
  if (typeof detalhe === 'string') return detalhe
  if (Array.isArray(detalhe)) return detalhe.map((d) => d.msg).join('; ')
  if (err?.code === 'ERR_NETWORK') return 'API fora do ar. Verifique se o servidor FastAPI está rodando.'
  return 'Erro inesperado ao falar com a API.'
}
