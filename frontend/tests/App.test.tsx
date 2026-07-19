import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { App } from '../src/App'
import type { PublishedPortfolioClient } from '../src/api/portfolio'

const run = {
  id: 'run-success-a', status: 'succeeded', started_at: '2026-07-19T12:00:00Z',
  completed_at: '2026-07-19T12:00:01Z', release_sha: 'release-a',
  effective_config_hash: 'config-a', failure_code: null, failure_detail: null,
  publication_id: 'publication-a', steps: [],
}
const freshness = { as_of: '2026-07-19T12:00:00Z', status: 'stale', serving_last_success: true }
const client: PublishedPortfolioClient = {
  getPortfolio: async () => ({
    run, freshness,
    data: {
      publication_id: 'publication-a', snapshot_id: 'snapshot-a',
      provider: 'deterministic_fake_broker', account_count: 1,
      equity_position_count: 1, option_leg_count: 2,
      accounts: [{
        id: 'account-a', external_account_id: 'taxable-001',
        provider: 'deterministic_fake_broker', account_type: 'taxable',
        display_name: 'Primary Taxable', currency: 'USD', observed_at: freshness.as_of,
      }],
    },
  }),
  getPositions: async () => ({
    run, freshness,
    data: {
      publication_id: 'publication-a', snapshot_id: 'snapshot-a',
      equity_positions: [{
        account_id: 'account-a', symbol: 'AAPL', quantity: '12', average_cost: '172.50',
        observed_at: freshness.as_of, original_provider: 'deterministic_fake_broker',
      }],
      option_legs: [
        { account_id: 'account-a', underlying_symbol: 'AAPL', option_symbol: 'AAPL-LONG', option_type: 'call', strike: '200', expiration: '2026-09-18', quantity: '1', side: 'long', average_price: '8.40', observed_at: freshness.as_of, original_provider: 'deterministic_fake_broker' },
        { account_id: 'account-a', underlying_symbol: 'AAPL', option_symbol: 'AAPL-SHORT', option_type: 'call', strike: '210', expiration: '2026-09-18', quantity: '1', side: 'short', average_price: '5.10', observed_at: freshness.as_of, original_provider: 'deterministic_fake_broker' },
      ],
    },
  }),
}

describe('App', () => {
  it('renders the published run, freshness, accounts, equities, and option legs', async () => {
    render(<App client={client} />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading')
    expect(await screen.findByText('run-success-a')).toBeInTheDocument()
    expect(screen.getByText('stale')).toBeInTheDocument()
    expect(screen.getByText('Serving last successful publication')).toBeInTheDocument()
    expect(screen.getByText('Primary Taxable')).toBeInTheDocument()
    expect(screen.getByText('12 shares')).toBeInTheDocument()
    expect(screen.getByText('long · 1 · strike 200')).toBeInTheDocument()
    expect(screen.getByText('short · 1 · strike 210')).toBeInTheDocument()
  })

  it('renders unavailable and error states', async () => {
    const unavailable: PublishedPortfolioClient = {
      getPortfolio: async () => Promise.reject({ status: 404 }), getPositions: client.getPositions,
    }
    const { unmount } = render(<App client={unavailable} />)
    expect(await screen.findByText('No published portfolio is available.')).toBeInTheDocument()
    unmount()
    const failed: PublishedPortfolioClient = {
      getPortfolio: async () => Promise.reject(new Error('down')), getPositions: client.getPositions,
    }
    render(<App client={failed} />)
    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })
})
