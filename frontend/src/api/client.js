import axios from 'axios'

const apiClient = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

export const api = {
  // Config
  getConfig: () => apiClient.get('/config').then(res => res.data),

  // Threads
  getThreads: () => apiClient.get('/research/threads').then(res => res.data),

  // Research Status
  getStatus: (threadId) => apiClient.get(`/research/${threadId}/status`).then(res => res.data),

  // Checkpoint History
  getHistory: (threadId) => apiClient.get(`/research/${threadId}/history`).then(res => res.data),

  // Inspect Checkpoint
  inspectCheckpoint: (threadId, checkpointId = null) => {
    const params = checkpointId ? { checkpoint_id: checkpointId } : {}
    return apiClient.get(`/research/${threadId}/inspect`, { params }).then(res => res.data)
  },

  // Start new research (prepares initial state)
  startResearch: (topic, threadId = null) =>
    apiClient.post('/research/run', { topic, thread_id: threadId }).then(res => res.data),

  // Fork Branch
  forkResearch: (payload) =>
    apiClient.post('/research/fork', payload).then(res => res.data),

  // Build SSE Stream URL
  getStreamUrl: (threadId, { action = 'run', topic = '', approve = true, plan = '' } = {}) => {
    const params = new URLSearchParams()
    params.set('action', action)
    if (topic) params.set('topic', topic)
    if (action === 'resume') {
      params.set('approve', approve ? 'true' : 'false')
      if (plan) params.set('plan', plan)
    }
    return `/api/research/${threadId}/stream?${params.toString()}`
  },
}

export default api
