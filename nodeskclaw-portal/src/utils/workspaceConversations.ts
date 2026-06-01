import type { Conversation, GroupChatMessage } from '@/stores/workspace'

export function resolveActiveConversationId(conversations: Conversation[], currentId: string): string {
  if (currentId && conversations.some((conversation) => conversation.id === currentId)) {
    return currentId
  }
  return conversations.find((conversation) => conversation.is_blackboard_group)?.id || conversations[0]?.id || ''
}

export function isBlackboardConversation(conversations: Conversation[], conversationId?: string): boolean {
  if (!conversationId) return false
  return conversations.some((conversation) => conversation.id === conversationId && conversation.is_blackboard_group)
}

export function shouldShowMessageInConversation(
  message: GroupChatMessage,
  conversationId: string | undefined,
  conversations: Conversation[],
): boolean {
  if (!conversationId) return true
  if (message.conversation_id === conversationId) return true
  return !message.conversation_id && isBlackboardConversation(conversations, conversationId)
}

export function filterMessagesForConversation(
  messages: GroupChatMessage[],
  conversationId: string | undefined,
  conversations: Conversation[],
): GroupChatMessage[] {
  return messages.filter((message) => shouldShowMessageInConversation(message, conversationId, conversations))
}
