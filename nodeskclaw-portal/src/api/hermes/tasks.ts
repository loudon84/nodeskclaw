import api from '@/services/api'

export interface HermesTask {
  id: string
  task_no: string
  skill_id: string
  tool_name: string
  status: string
  created_at: string
  updated_at: string
}

export interface TaskListParams {
  page?: number
  page_size?: number
  skill_id?: string
  status?: string
}

export async function listTasks(params?: TaskListParams) {
  const { data } = await api.get('/hermes/tasks', { params })
  return data
}
