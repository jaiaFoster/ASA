import { useEffect, useState } from 'react'

import {
  publishedPortfolioClient,
  type PortfolioEnvelope,
  type PositionsEnvelope,
  type PublishedPortfolioClient,
} from './api/portfolio'
import './styles.css'

type DashboardData = { portfolio: PortfolioEnvelope; positions: PositionsEnvelope }
type ViewState =
  | { kind: 'loading' }
  | { kind: 'success'; value: DashboardData }
  | { kind: 'unavailable' }
  | { kind: 'error' }

export function App({ client = publishedPortfolioClient }: { client?: PublishedPortfolioClient }) {
  const [state, setState] = useState<ViewState>({ kind: 'loading' })

  useEffect(() => {
    let active = true
    Promise.all([client.getPortfolio(), client.getPositions()]).then(
      ([portfolio, positions]) => active && setState({ kind: 'success', value: { portfolio, positions } }),
      (error: { status?: number }) => {
        if (active) setState(error.status === 404 ? { kind: 'unavailable' } : { kind: 'error' })
      },
    )
    return () => { active = false }
  }, [client])

  return (
    <main>
      <p className="eyebrow">ASA · published portfolio</p>
      <h1>Portfolio foundation</h1>
      {state.kind === 'loading' && <p role="status">Loading current publication…</p>}
      {state.kind === 'unavailable' && <p role="status">No published portfolio is available.</p>}
      {state.kind === 'error' && <p role="alert">Unable to reach the portfolio service.</p>}
      {state.kind === 'success' && <PortfolioDashboard {...state.value} />}
    </main>
  )
}

function PortfolioDashboard({ portfolio, positions }: DashboardData) {
  return (
    <div className="dashboard">
      <section className="run-banner" aria-label="Canonical run">
        <div><span>Canonical run</span><strong>{portfolio.run.id}</strong></div>
        <span className={`freshness ${portfolio.freshness.status}`}>{portfolio.freshness.status}</span>
        <div><span>As of</span><strong>{portfolio.freshness.as_of}</strong></div>
        {portfolio.freshness.serving_last_success && (
          <p className="last-success">Serving last successful publication</p>
        )}
      </section>

      <section className="summary" aria-label="Portfolio summary">
        <Metric label="Accounts" value={portfolio.data.account_count} />
        <Metric label="Equities" value={portfolio.data.equity_position_count} />
        <Metric label="Option legs" value={portfolio.data.option_leg_count} />
      </section>

      <section>
        <h2>Accounts</h2>
        {portfolio.data.accounts.map((account) => (
          <article key={account.id} className="account-card">
            <strong>{account.display_name}</strong>
            <span>{account.account_type} · {account.currency}</span>
            <small>{account.provider} · {account.external_account_id}</small>
          </article>
        ))}
      </section>

      <section>
        <h2>Equity positions</h2>
        <div className="position-list">
          {positions.data.equity_positions.map((position) => (
            <article key={`${position.account_id}-${position.symbol}`}>
              <strong>{position.symbol}</strong><span>{position.quantity} shares</span>
              <small>Average cost {position.average_cost ?? 'unavailable'} · {position.original_provider}</small>
            </article>
          ))}
        </div>
      </section>

      <section>
        <h2>Option legs</h2>
        <div className="position-list">
          {positions.data.option_legs.map((leg) => (
            <article key={leg.option_symbol}>
              <strong>{leg.underlying_symbol} {leg.option_type}</strong>
              <span>{leg.side} · {leg.quantity} · strike {leg.strike}</span>
              <small>{leg.expiration} · {leg.option_symbol} · {leg.original_provider}</small>
            </article>
          ))}
        </div>
      </section>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: number }) {
  return <div><span>{label}</span><strong>{value}</strong></div>
}
