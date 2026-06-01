import { describe, expect, it } from 'vitest'

import { getStatusDisplay } from './instanceStatus'

describe('getStatusDisplay', () => {
  it('returns mapped status config for known statuses', () => {
    expect(getStatusDisplay('ready')).toEqual({
      key: 'ready',
      color: 'text-green-400',
      bgColor: 'bg-green-400',
      pulse: false,
    })
  })

  it('falls back to neutral config for unknown statuses', () => {
    expect(getStatusDisplay('unknown')).toEqual({
      key: 'unknown',
      color: 'text-gray-400',
      bgColor: 'bg-gray-400',
      pulse: false,
    })
  })
})
