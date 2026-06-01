import { describe, expect, it } from 'vitest'

import type { Conversation, GroupChatMessage } from '@/stores/workspace'
import {
  filterMessagesForConversation,
  resolveActiveConversationId,
  shouldShowMessageInConversation,
} from './workspaceConversations'

function conversation(id: string, isBlackboard = false): Conversation {
  return {
    id,
    workspace_id: 'ws-1',
    name: id,
    is_blackboard_group: isBlackboard,
    member_node_ids: [],
    last_message_at: null,
    last_message_preview: null,
    created_at: null,
  }
}

function message(id: string, conversationId?: string): GroupChatMessage {
  return {
    id,
    sender_type: 'agent',
    sender_id: 'agent-1',
    sender_name: 'Agent',
    content: id,
    message_type: 'chat',
    created_at: '2026-05-08T00:00:00.000Z',
    conversation_id: conversationId,
  }
}

describe('workspaceConversations', () => {
  it('keeps active conversation when it still exists', () => {
    const conversations = [conversation('blackboard', true), conversation('normal')]

    expect(resolveActiveConversationId(conversations, 'normal')).toBe('normal')
  })

  it('falls back to blackboard conversation when active conversation disappears', () => {
    const conversations = [conversation('normal'), conversation('blackboard', true)]

    expect(resolveActiveConversationId(conversations, 'missing')).toBe('blackboard')
  })

  it('shows legacy unscoped messages only in blackboard conversation', () => {
    const conversations = [conversation('blackboard', true), conversation('normal')]
    const legacy = message('legacy')
    const blackboard = message('blackboard', 'blackboard')
    const normal = message('normal', 'normal')

    expect(shouldShowMessageInConversation(legacy, 'blackboard', conversations)).toBe(true)
    expect(shouldShowMessageInConversation(legacy, 'normal', conversations)).toBe(false)
    expect(filterMessagesForConversation([legacy, blackboard, normal], 'normal', conversations).map(m => m.id))
      .toEqual(['normal'])
  })
})
