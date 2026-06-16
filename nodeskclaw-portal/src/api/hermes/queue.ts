import api from '@/services/api'
import type { HermesTask } from '@/api/hermes/tasks'

function unwrapEnvelope<T>(body: unknown): T {
  if (body && typeof body === 'object' && 'data' in (body as Record<string, unknown>)) {
    return (body as { data: T }).data
  }
  return body as T
}

export interface QueueStats {
  queued: number
  accepted: number
  running: number
  failed: number
  timeout: number
}

export interface QueueTaskListResult {
  items: HermesTask[]
  total: number
  page: number
  page_size: number
}

export async function getQueueStats(): Promise<QueueStats> {
  const { data } = await api.get('/hermes/queue/stats')
  return unwrapEnvelope<QueueStats>(data)
}

export async function listQueueTasks(params?: Record<string, string | number | undefined>): Promise<QueueTaskListResult> {
  const { data } = await api.get('/hermes/queue/tasks', { params })
  return unwrapEnvelope<QueueTaskListResult>(data)
}

export async function setTaskPriority(taskId: string, priority: number) {
  const { data } = await api.post(`/hermes/queue/tasks/${taskId}/priority`, { priority })
  return unwrapEnvelope<HermesTask>(data)
}

export async function requeueQueueTask(taskId: string) {
  const { data } = await api.post(`/hermes/queue/tasks/${taskId}/requeue`)
  return unwrapEnvelope<HermesTask>(data)
}

export async function markFailedQueueTask(taskId: string, errorMessage?: string) {
  const { data } = await api.post(`/hermes/queue/tasks/${taskId}/mark-failed`, {
    error_message: errorMessage ?? 'Marked failed by operator',
  })
  return unwrapEnvelope<HermesTask>(data)
}
