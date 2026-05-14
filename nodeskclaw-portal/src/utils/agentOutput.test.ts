import { describe, expect, it } from 'vitest'
import { AgentThinkingStreamFilter, stripAgentThinkingBlocks, visibleAgentContent } from './agentOutput'

describe('agentOutput', () => {
  it('keeps normal content unchanged', () => {
    expect(stripAgentThinkingBlocks('正常回复')).toBe('正常回复')
  })

  it('removes single multiline think block', () => {
    expect(stripAgentThinkingBlocks('前文\n<think>\nEnglish reasoning\n</think>\n正文')).toBe('前文\n正文')
  })

  it('removes multiple blocks with mixed tag case', () => {
    expect(stripAgentThinkingBlocks('<THINK>one</THINK>答复<think>two</think>结束')).toBe('答复结束')
  })

  it('drops unclosed think block', () => {
    expect(stripAgentThinkingBlocks('正文<think>unfinished')).toBe('正文')
  })

  it('only sanitizes agent content by sender type', () => {
    const content = '用户写的 <think>不是思考</think>'
    expect(visibleAgentContent('user', content)).toBe(content)
    expect(visibleAgentContent('agent', content)).toBe('用户写的')
  })

  it('filters split streaming think tags without leaking content', () => {
    const filter = new AgentThinkingStreamFilter()

    expect(filter.feed('开头 <thi')).toBe('开头 ')
    expect(filter.feed('nk>hidden')).toBe('')
    expect(filter.feed(' text</thi')).toBe('')
    expect(filter.feed('nk>正文')).toBe('正文')
    expect(filter.flush()).toBe('')
  })

  it('uses final content to remove completed stream reasoning', () => {
    const filter = new AgentThinkingStreamFilter()

    expect(filter.feed('<think>hidden')).toBe('')
    expect(filter.flush()).toBe('')
  })
})
