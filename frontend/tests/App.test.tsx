import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { App } from '../src/App'
import type { MarketQuoteClient } from '../src/api/market'

const quote = {
  symbol: 'AAPL',
  price: '189.42',
  currency: 'USD',
  observed_at: '2026-07-19T12:00:00Z',
  received_at: '2026-07-19T12:00:01Z',
  provenance: {
    selected_provider: 'deterministic_fake',
    original_provider: 'deterministic_fake',
    cache_status: 'miss',
    freshness_status: 'fresh',
    fallback_reason: null,
    provider_request_id: 'fake-123',
  },
}

describe('App', () => {
  it('renders every required API field without recalculating it', async () => {
    const client: MarketQuoteClient = { getLatestQuote: async () => quote }
    render(<App client={client} />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading')
    expect(await screen.findByText('AAPL')).toBeInTheDocument()
    expect(screen.getByText('189.42')).toBeInTheDocument()
    expect(screen.getByText('USD')).toBeInTheDocument()
    expect(screen.getByText('2026-07-19T12:00:00Z')).toBeInTheDocument()
    expect(screen.getByText('deterministic_fake')).toBeInTheDocument()
    expect(screen.getByText('fresh')).toBeInTheDocument()
  })

  it('renders unavailable and error states', async () => {
    const unavailable: MarketQuoteClient = { getLatestQuote: async () => Promise.reject({ status: 404 }) }
    const { unmount } = render(<App client={unavailable} />)
    expect(await screen.findByText('AAPL quote unavailable.')).toBeInTheDocument()
    unmount()
    const failed: MarketQuoteClient = { getLatestQuote: async () => Promise.reject(new Error('down')) }
    render(<App client={failed} />)
    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })
})
