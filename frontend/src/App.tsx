import { useEffect, useState } from 'react'

import { marketQuoteClient, type MarketQuoteClient, type QuoteResponse } from './api/market'
import './styles.css'

type ViewState =
  | { kind: 'loading' }
  | { kind: 'success'; quote: QuoteResponse }
  | { kind: 'unavailable' }
  | { kind: 'error' }

export function App({ client = marketQuoteClient }: { client?: MarketQuoteClient }) {
  const [state, setState] = useState<ViewState>({ kind: 'loading' })

  useEffect(() => {
    let active = true
    client.getLatestQuote('AAPL').then(
      (quote) => active && setState({ kind: 'success', quote }),
      (error: { status?: number }) => {
        if (active) setState(error.status === 404 ? { kind: 'unavailable' } : { kind: 'error' })
      },
    )
    return () => { active = false }
  }, [client])

  return (
    <main>
      <p className="eyebrow">ASA · canonical market data</p>
      <h1>Market observation</h1>
      {state.kind === 'loading' && <p role="status">Loading latest quote…</p>}
      {state.kind === 'unavailable' && <p role="status">AAPL quote unavailable.</p>}
      {state.kind === 'error' && <p role="alert">Unable to reach the market data service.</p>}
      {state.kind === 'success' && <QuoteCard quote={state.quote} />}
    </main>
  )
}

function QuoteCard({ quote }: { quote: QuoteResponse }) {
  return (
    <article aria-label={`${quote.symbol} quote`}>
      <div className="quote-heading">
        <span className="symbol">{quote.symbol}</span>
        <span className={`freshness ${quote.provenance.freshness_status}`}>
          {quote.provenance.freshness_status}
        </span>
      </div>
      <p className="price">{quote.price} <span>{quote.currency}</span></p>
      <dl>
        <div><dt>Observed</dt><dd>{quote.observed_at}</dd></div>
        <div><dt>Provider</dt><dd>{quote.provenance.selected_provider}</dd></div>
      </dl>
    </article>
  )
}
