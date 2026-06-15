import api from '@/services/api'

function unwrapEnvelope<T>(body: unknown): T {
  if (body && typeof body === 'object' && 'data' in (body as Record<string, unknown>)) {
    return (body as { data: T }).data
  }
  return body as T
}

export interface HermesTask {
  id: string
  task_no: string
  skill_id: string
  tool_name: string
  agent_id: string | null
  profile_id: string | null
  workspace_id: string | null
  status: string
  hermes_run_id: string | null
  event_url: string | null
  artifact_url: string | null
  error_code: string | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface TaskListParams {
  page?: number
  page_size?: number
  skill_id?: string
  status?: string
  tool_name?: string
  agent_id?: string
}

export interface TaskListResult {
  items: HermesTask[]
  total: number
  page: number
  page_size: number
}

export interface TaskEvent {
  task_id: string
  event_type: string
  event_seq: number
  payload: Record<string, unknown> | null
  created_at: string | null
}

export async function listTasks(params?: TaskListParams): Promise<TaskListResult> {
  const { data } = await api.get('/hermes/tasks', { params })
  return unwrapEnvelope<TaskListResult>(data)
}

export async function getTask(taskId: string): Promise<HermesTask> {
  const { data } = await api.get(`/hermes/tasks/${taskId}`)
  return unwrapEnvelope<HermesTask>(data)
}

export async function cancelTask(taskId: string): Promise<HermesTask> {
  const { data } = await api.post(`/hermes/tasks/${taskId}/cancel`)
  return unwrapEnvelope<HermesTask>(data)
}

export async function retryTask(taskId: string): Promise<HermesTask> {
  const { data } = await api.post(`/hermes/tasks/${taskId}/retry`)
  return unwrapEnvelope<HermesTask>(data)
}

export async function listTaskArtifacts(taskId: string) {
  const { data } = await api.get(`/hermes/tasks/${taskId}/artifacts`)
  return unwrapEnvelope<unknown[]>(data)
}
