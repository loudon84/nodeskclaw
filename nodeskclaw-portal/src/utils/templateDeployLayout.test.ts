import { describe, expect, it } from 'vitest'

import {
  initialAgentPositions,
  positionsPayload,
  selectedLayoutAgents,
} from '@/utils/templateDeployLayout'
import {
  allSelectableKeys,
  agentSelectableKey,
  keysToSelectedIndices,
} from '@/utils/templateTopology'

describe('templateDeployLayout', () => {
  it('uses original agent indices instead of coordinate keys', () => {
    const specs = [
      { display_name: 'A', hex_q: 1, hex_r: 0 },
      { display_name: 'B', hex_q: 1, hex_r: 0 },
      { display_name: 'C' },
    ]

    const keys = allSelectableKeys(specs)
    expect(keys.has(agentSelectableKey(0))).toBe(true)
    expect(keys.has(agentSelectableKey(1))).toBe(true)
    expect(keys.has(agentSelectableKey(2))).toBe(true)

    keys.delete(agentSelectableKey(1))
    expect(keysToSelectedIndices(specs, keys)).toEqual([0, 2])
  })

  it('omits missing coordinates until the user places the agent', () => {
    const specs = [
      { display_name: 'A', hex_q: 1, hex_r: 0 },
      { display_name: 'B' },
    ]
    const positions = initialAgentPositions(specs)

    expect(positionsPayload([0, 1], positions)).toEqual([
      { agent_index: 0, hex_q: 1, hex_r: 0 },
    ])

    positions.set(1, { q: 2, r: -1 })
    expect(positionsPayload([0, 1], positions)).toEqual([
      { agent_index: 0, hex_q: 1, hex_r: 0 },
      { agent_index: 1, hex_q: 2, hex_r: -1 },
    ])
  })

  it('builds layout agents with stable agent index ids', () => {
    const specs = [
      { display_name: 'A', hex_q: 1, hex_r: 0 },
      { display_name: 'B', hex_q: 2, hex_r: 0 },
    ]
    const agents = selectedLayoutAgents(specs, [1], initialAgentPositions(specs))

    expect(agents).toHaveLength(1)
    expect(agents[0].instance_id).toBe(agentSelectableKey(1))
    expect(agents[0].hex_q).toBe(2)
  })
})
