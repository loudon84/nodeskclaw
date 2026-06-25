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
  installation_id: string | null
  status: string
  hermes_run_id: string | null
  event_url: string | null
  artifact_url: string | null
  error_code: string | null
  error_message: string | null
  result_summary: string | null
  created_at: string
  updated_at: string
  priority?: number
  retry_count?: number
  max_retry?: number
  queue_reason?: string | null
  user_id?: string | null
}

export interface TaskListParams {
  page?: number
  page_size?: number
  skill_id?: string
  status?: string
  tool_name?: string
  agent_id?: string
  workspace_id?: string
  user_id?: string
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

export interface TaskTimelineItem {
  event_seq: number
  event_type: string
  title: string
  timestamp: string | null
  payload: Record<string, unknown> | null
}

export interface TaskTimeline {
  task_id: string
  task_no: string
  status: string
  items: TaskTimelineItem[]
}

export async function listTasks(params?: TaskListParams): Promise<TaskListResult> {
  const { data } = await api.get('/hermes/tasks', { params })
  return unwrapEnvelope<TaskListResult>(data)
}

export async function getTask(taskId: string): Promise<HermesTask> {
  const { data } = await api.get(`/hermes/tasks/${taskId}`)
  return unwrapEnvelope<HermesTask>(data)
}

export async function getTaskTimeline(taskId: string): Promise<TaskTimeline> {
  const { data } = await api.get(`/hermes/tasks/${taskId}/timeline`)
  return unwrapEnvelope<TaskTimeline>(data)
}

export async function cancelTask(taskId: string): Promise<HermesTask> {
  const { data } = await api.post(`/hermes/tasks/${taskId}/cancel`)
  return unwrapEnvelope<HermesTask>(data)
}

export async function retryTask(taskId: string): Promise<HermesTask> {
  const { data } = await api.post(`/hermes/tasks/${taskId}/retry`)
  return unwrapEnvelope<HermesTask>(data)
}

export async function listTaskArtifacts(taskId: string): Promise<TaskArtifactsResponse> {
  const { data } = await api.get(`/hermes/tasks/${taskId}/artifacts`)
  const body = data as Record<string, unknown>
  return {
    items: Array.isArray(body.data) ? (body.data as TaskArtifact[]) : [],
    server_artifacts: (body.server_artifacts as ServerArtifact[]) ?? [],
    artifact_mode: (body.artifact_mode as string) ?? 'pull_only',
  }
}

export interface TaskArtifact {
  id: string
  task_id: string | null
  file_name: string
  relative_path: string | null
  content_type: string | null
  artifact_type: string | null
  size_bytes: number | null
  preview_supported?: boolean
  metadata_json?: Record<string, unknown> | null
}

export interface ServerArtifact {
  artifact_id: string
  name: string
  type: string
  mime_type: string | null
  stored: boolean
  store: string
  download_url: string
  preview_url: string
  suggested_workspace_path: string | null
  workspace_saved: boolean
  kb_status: string
}

export interface TaskArtifactsResponse {
  items: TaskArtifact[]
  server_artifacts: ServerArtifact[]
  artifact_mode: string
}

export interface ArtifactRescanResult {
  task_id: string
  artifact_count: number
  artifacts: Array<{
    id: string
    filename: string
    artifact_type: string | null
    mime_type: string | null
    relative_path: string | null
    size_bytes: number | null
  }>
  warning?: string | null
}

export async function rescanTaskArtifacts(taskId: string, force = false): Promise<ArtifactRescanResult> {
  const { data } = await api.post(`/hermes/tasks/${taskId}/artifacts/rescan`, { force })
  return unwrapEnvelope<ArtifactRescanResult>(data)
}

export async function requeueTask(taskId: string): Promise<HermesTask> {
  const { data } = await api.post(`/hermes/tasks/${taskId}/requeue`)
  return unwrapEnvelope<HermesTask>(data)
}

export async function setTaskPriority(taskId: string, priority: number): Promise<HermesTask> {
  const { data } = await api.post(`/hermes/tasks/${taskId}/priority`, { priority })
  return unwrapEnvelope<HermesTask>(data)
}

export async function markTaskFailed(taskId: string, errorMessage?: string): Promise<HermesTask> {
  const { data } = await api.post(`/hermes/tasks/${taskId}/mark-failed`, {
    error_message: errorMessage ?? 'Marked failed by operator',
  })
  return unwrapEnvelope<HermesTask>(data)
}
