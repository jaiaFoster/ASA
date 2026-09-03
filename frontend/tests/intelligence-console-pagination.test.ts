import { describe, expect, it } from 'vitest'

// Static Intelligence Console code is packaged by the backend, outside this
// TypeScript project's source root.
// @ts-expect-error JavaScript module intentionally has no separate declaration file.
import { collectCompleteScreeningState } from '../../asa/ui/static/pagination.js'

type Row = { signal_id: string; symbol: string }

function pages(rows: Row[], snapshots: string[] = ['snapshot-a']) {
  let call = 0
  return async (limit: number, offset: number) => {
    const snapshot_identity = snapshots[Math.min(call++, snapshots.length - 1)]
    return {
      data: {
        results: rows.slice(offset, offset + limit), total: rows.length,
        limit, offset, snapshot_identity,
      },
      apiVersion: 'v1',
    }
  }
}

function rows(counts: number[]): Row[] {
  return counts.flatMap((count, signal) =>
    Array.from({ length: count }, (_, index) => ({ signal_id: `signal-${signal}`, symbol: `${index}` })),
  )
}

describe('Intelligence Console complete latest-state pagination', () => {
  it.each([501, 1000, 1001])('loads all %i rows without alphabetical starvation', async (total) => {
    const source = rows([500, Math.max(0, total - 501), 1])
    const result = await collectCompleteScreeningState(pages(source))

    expect(result.data.results).toEqual(source)
    expect(result.data.total).toBe(total)
    expect(new Set(result.data.results.map((item: Row) => item.signal_id))).toContain('signal-2')
  })

  it('rejects duplicate identities across exact page boundaries', async () => {
    const source = rows([501])
    const fetchPage = pages(source)
    await expect(collectCompleteScreeningState(async (limit: number, offset: number) => {
      const response = await fetchPage(limit, offset)
      if (offset === 500) response.data.results[0] = source[0]
      return response
    })).rejects.toThrow('Duplicate screening identity')
  })

  it('rejects a refresh that changes the snapshot between pages', async () => {
    await expect(
      collectCompleteScreeningState(pages(rows([501]), ['snapshot-a', 'snapshot-b'])),
    ).rejects.toThrow('Screening state changed during pagination')
  })
})
