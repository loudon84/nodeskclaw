import api from '@/services/api'

function unwrapEnvelope<T>(body: unknown): T {
  if (body && typeof body === 'object' && 'data' in (body as Record<string, unknown>)) {
    return (body as { data: T }).data
  }
  return body as T
}

export interface RuntimeControls {
  worker: { paused: boolean; reason: string | null }
  queue: { paused: boolean; reason: string | null }
}

export async function getRuntimeControls(): Promise<RuntimeControls> {
  const { data } = await api.get('/hermes/runtime/controls')
  return unwrapEnvelope<RuntimeControls>(data)
}

export async function pauseWorker(reason?: string): Promise<RuntimeControls> {
  const { data } = await api.post('/hermes/runtime/worker/pause', { reason: reason ?? null })
  return unwrapEnvelope<RuntimeControls>(data)
}

export async function resumeWorker(): Promise<RuntimeControls> {
  const { data } = await api.post('/hermes/runtime/worker/resume')
  return unwrapEnvelope<RuntimeControls>(data)
}

export async function pauseQueue(reason?: string): Promise<RuntimeControls> {
  const { data } = await api.post('/hermes/runtime/queue/pause', { reason: reason ?? null })
  return unwrapEnvelope<RuntimeControls>(data)
}

export async function resumeQueue(): Promise<RuntimeControls> {
  const { data } = await api.post('/hermes/runtime/queue/resume')
  return unwrapEnvelope<RuntimeControls>(data)
}

export async function clearStaleLocks(): Promise<{ cleared: number }> {
  const { data } = await api.post('/hermes/runtime/locks/clear-stale')
  return unwrapEnvelope<{ cleared: number }>(data)
}

export async function requeueRuntimeTask(taskId: string) {
  const { data } = await api.post(`/hermes/runtime/tasks/${taskId}/requeue`)
  return unwrapEnvelope(data)
}

export async function markFailedRuntimeTask(taskId: string) {
  const { data } = await api.post(`/hermes/runtime/tasks/${taskId}/mark-failed`)
  return unwrapEnvelope(data)
}
