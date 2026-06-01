const OPEN_TAG_RE = /<\s*think\b[^>]*>/i
const CLOSE_TAG_RE = /<\/\s*think\s*>/i
const THINK_BLOCK_RE = /<\s*think\b[^>]*>[\s\S]*?(?:<\/\s*think\s*>|$)/gi
const MAX_TAG_TAIL = 64

export function stripAgentThinkingBlocks(text: string): string {
  if (!text) return text
  if (!OPEN_TAG_RE.test(text) && !CLOSE_TAG_RE.test(text)) return text

  return text
    .replace(THINK_BLOCK_RE, '')
    .replace(/<\/\s*think\s*>/gi, '')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{2,}/g, '\n')
    .trim()
}

export function visibleAgentContent(senderType: string, content: string): string {
  if (senderType === 'agent') return stripAgentThinkingBlocks(content)
  return content
}

function partialOpenSuffix(text: string): string {
  const start = Math.max(0, text.length - MAX_TAG_TAIL)
  for (let index = start; index < text.length; index += 1) {
    const suffix = text.slice(index)
    if (looksLikePartialOpenTag(suffix)) return suffix
  }
  return ''
}

function looksLikePartialOpenTag(suffix: string): boolean {
  if (!suffix.startsWith('<') || suffix.includes('>')) return false

  const body = suffix.slice(1).trimStart().toLowerCase()
  if (!body) return true
  if ('think'.startsWith(body)) return true
  if (body.startsWith('think')) {
    if (body.length === 'think'.length) return true
    const next = body['think'.length]
    return !(/[a-z0-9_-]/i.test(next || ''))
  }
  return false
}

export class AgentThinkingStreamFilter {
  private buffer = ''
  private insideThink = false

  feed(chunk: string): string {
    if (!chunk) return ''
    this.buffer += chunk
    return this.drain(false)
  }

  flush(): string {
    return this.drain(true)
  }

  private drain(final: boolean): string {
    const output: string[] = []

    while (this.buffer) {
      if (this.insideThink) {
        const closeMatch = this.buffer.match(CLOSE_TAG_RE)
        if (!closeMatch || closeMatch.index === undefined) {
          if (final) {
            this.buffer = ''
            this.insideThink = false
          } else {
            this.buffer = this.buffer.slice(-MAX_TAG_TAIL)
          }
          break
        }
        this.buffer = this.buffer.slice(closeMatch.index + closeMatch[0].length)
        this.insideThink = false
        continue
      }

      const openMatch = this.buffer.match(OPEN_TAG_RE)
      if (openMatch && openMatch.index !== undefined) {
        output.push(this.buffer.slice(0, openMatch.index))
        this.buffer = this.buffer.slice(openMatch.index + openMatch[0].length)
        this.insideThink = true
        continue
      }

      const keep = partialOpenSuffix(this.buffer)
      if (keep) {
        output.push(this.buffer.slice(0, -keep.length))
        this.buffer = final ? '' : keep
      } else {
        output.push(this.buffer)
        this.buffer = ''
      }
      break
    }

    return output.join('')
  }
}
