import { i18n } from './index'

type ApiErrorData = {
  message?: string
  message_key?: string
  message_params?: Record<string, unknown>
  error_code?: number
}

function readErrorData(error: unknown): ApiErrorData {
  const data = (error as any)?.response?.data
  if (data && typeof data === 'object') {
    return data as ApiErrorData
  }
  return {}
}

const GENERIC_KEY_PREFIX = 'errors.common.'

const PUBLISH_PRECONDITION_KEYS = new Set([
  'errors.expert.publish_precondition_failed',
  'errors.expert.team_publish_precondition_failed',
])

function formatPublishIssues(issues: unknown): string {
  const list = Array.isArray(issues) ? issues : []
  const labels = list.map((issue) => {
    const key = `errors.expert.publish_issues.${String(issue)}`
    return i18n.global.te(key) ? i18n.global.t(key) : String(issue)
  })
  return labels.join('、')
}

export function resolveApiErrorMessage(error: unknown, fallback = ''): string {
  const { message_key, message, message_params } = readErrorData(error)
  const hasSpecificMessage = !!(message && message.trim())
  const isGenericKey = message_key?.startsWith(GENERIC_KEY_PREFIX)

  if (message_key && PUBLISH_PRECONDITION_KEYS.has(message_key) && message_params?.issues) {
    return i18n.global.t(message_key, {
      issues: formatPublishIssues(message_params.issues),
    })
  }

  if (isGenericKey && hasSpecificMessage) {
    return message!.trim()
  }
  if (message_key && i18n.global.te(message_key)) {
    return i18n.global.t(message_key, message_params ?? {})
  }
  if (hasSpecificMessage) return message!.trim()
  if (fallback) return fallback
  if (i18n.global.te('errors.system.internal_error')) {
    return i18n.global.t('errors.system.internal_error')
  }
  return 'Internal server error'
}
