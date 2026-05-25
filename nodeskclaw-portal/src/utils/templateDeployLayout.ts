import type { AgentBrief } from '@/stores/workspace'
import { agentSelectableKey } from '@/utils/templateTopology'

export interface TemplateAgentPosition {
  agent_index: number
  hex_q: number
  hex_r: number
}

export interface TemplateLayoutIssue {
  code: string
  message: string
  agent_index?: number
  hex_q?: number
  hex_r?: number
  conflict_with?: string
}

export interface TemplateLayoutCheckResult {
  can_deploy: boolean
  selected_agent_indices: number[]
  excluded_corridor_coords: number[][]
  agent_positions: TemplateAgentPosition[]
  issues: TemplateLayoutIssue[]
}

export function isIntegerCoord(value: unknown): value is number {
  return Number.isInteger(value)
}

export function initialAgentPositions(agentSpecs: Record<string, unknown>[]): Map<number, { q: number; r: number }> {
  const positions = new Map<number, { q: number; r: number }>()
  agentSpecs.forEach((spec, index) => {
    if (isIntegerCoord(spec.hex_q) && isIntegerCoord(spec.hex_r)) {
      positions.set(index, { q: spec.hex_q, r: spec.hex_r })
    }
  })
  return positions
}

export function positionsPayload(
  selectedAgentIndices: number[],
  positions: Map<number, { q: number; r: number }>,
): TemplateAgentPosition[] {
  return selectedAgentIndices
    .map((agentIndex) => {
      const pos = positions.get(agentIndex)
      if (!pos) return null
      return { agent_index: agentIndex, hex_q: pos.q, hex_r: pos.r }
    })
    .filter((item): item is TemplateAgentPosition => item !== null)
}

export function selectedLayoutAgents(
  agentSpecs: Record<string, unknown>[],
  selectedAgentIndices: number[],
  positions: Map<number, { q: number; r: number }>,
): AgentBrief[] {
  return selectedAgentIndices
    .map((agentIndex) => {
      const spec = agentSpecs[agentIndex]
      const pos = positions.get(agentIndex)
      if (!spec || !pos) return null
      return {
        instance_id: agentSelectableKey(agentIndex),
        name: (spec.display_name as string) || (spec.label as string) || '',
        display_name: (spec.display_name as string) || null,
        label: (spec.label as string) || null,
        slug: null,
        status: 'idle',
        hex_q: pos.q,
        hex_r: pos.r,
        sse_connected: false,
        theme_color: null,
      }
    })
    .filter((item): item is AgentBrief => item !== null)
}

export function agentIndicesWithIssues(issues: TemplateLayoutIssue[]): Set<number> {
  return new Set(
    issues
      .map(issue => issue.agent_index)
      .filter((index): index is number => typeof index === 'number'),
  )
}
