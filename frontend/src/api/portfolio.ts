import type { PortfolioEnvelope } from './generated/models/PortfolioEnvelope'
import type { PositionsEnvelope } from './generated/models/PositionsEnvelope'
import { DefaultService } from './generated/services/DefaultService'

export type { PortfolioEnvelope, PositionsEnvelope }

export interface PublishedPortfolioClient {
  getPortfolio(): Promise<PortfolioEnvelope>
  getPositions(): Promise<PositionsEnvelope>
}

export const publishedPortfolioClient: PublishedPortfolioClient = {
  getPortfolio: () => DefaultService.getPortfolio(),
  getPositions: () => DefaultService.getPositions(),
}
