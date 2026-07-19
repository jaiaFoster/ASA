import type { QuoteResponse } from './generated/models/QuoteResponse'
import { DefaultService } from './generated/services/DefaultService'

export type { QuoteResponse }

export interface MarketQuoteClient {
  getLatestQuote(symbol: string): Promise<QuoteResponse>
}

export const marketQuoteClient: MarketQuoteClient = {
  getLatestQuote: (symbol) => DefaultService.getLatestQuote(symbol),
}
