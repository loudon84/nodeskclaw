import type { TopologyInfo } from '@/stores/workspace'

export interface MentionCandidate {
  agentId: string
  agentName: string
}

type HexKey = string

const PROPAGATES: Record<string, boolean> = {
  corridor: true,
  blackboard: true,
  agent: false,
  human: false,
}

function hexKey(q: number, r: number): HexKey {
  return `${q},${r}`
}

function buildGraphMaps(topology: TopologyInfo) {
  const adj = new Map<HexKey, HexKey[]>()
  const nodeAt = new Map<HexKey, { nodeType: string; entityId: string | null; displayName: string | null }>()

  for (const n of topology.nodes) {
    nodeAt.set(hexKey(n.hex_q, n.hex_r), {
      nodeType: n.node_type,
      entityId: n.entity_id,
      displayName: n.display_name,
    })
  }

  for (const e of topology.edges) {
    const a = hexKey(e.a_q, e.a_r)
    const b = hexKey(e.b_q, e.b_r)
    if (!adj.has(a)) adj.set(a, [])
    if (!adj.has(b)) adj.set(b, [])
    adj.get(a)!.push(b)
    adj.get(b)!.push(a)
  }

  return { adj, nodeAt }
}

function bfsCollectAgents(
  startKey: HexKey,
  adj: Map<HexKey, HexKey[]>,
  nodeAt: Map<HexKey, { nodeType: string; entityId: string | null; displayName: string | null }>,
  seen: Set<string>,
): MentionCandidate[] {
  const results: MentionCandidate[] = []
  const visited = new Set<HexKey>([startKey])
  const queue: HexKey[] = [startKey]

  while (queue.length > 0) {
    const current = queue.shift()!
    for (const neighbor of adj.get(current) ?? []) {
      if (visited.has(neighbor)) continue
      visited.add(neighbor)
      const node = nodeAt.get(neighbor)
      if (!node) continue

      if (node.nodeType === 'agent' && node.entityId && !seen.has(node.entityId)) {
        seen.add(node.entityId)
        results.push({ agentId: node.entityId, agentName: node.displayName ?? '' })
      }

      if (PROPAGATES[node.nodeType]) {
        queue.push(neighbor)
      }
    }
  }

  return results
}

/**
 * Compute which agents should appear in the mention candidate list.
 *
 * Level 1: BFS from blackboard (0,0) — agents directly reachable.
 * Level 2: For each already-mentioned agent, BFS from its hex — newly reachable agents.
 *
 * No topology (null or no edges) returns all agents from the topology nodes.
 */
export function computeMentionCandidates(
  topology: TopologyInfo | null,
  existingMentionIds: Set<string>,
): MentionCandidate[] {
  if (!topology) return []

  if (topology.edges.length === 0) {
    return topology.nodes
      .filter(n => n.node_type === 'agent' && n.entity_id)
      .map(n => ({ agentId: n.entity_id!, agentName: n.display_name ?? '' }))
  }

  const { adj, nodeAt } = buildGraphMaps(topology)
  const seen = new Set<string>()

  const level1 = bfsCollectAgents(hexKey(0, 0), adj, nodeAt, seen)

  const level2: MentionCandidate[] = []
  for (const mentionId of existingMentionIds) {
    const entry = topology.nodes.find(n => n.entity_id === mentionId)
    if (!entry) continue
    const results = bfsCollectAgents(hexKey(entry.hex_q, entry.hex_r), adj, nodeAt, seen)
    level2.push(...results)
  }

  return [...level1, ...level2]
}
