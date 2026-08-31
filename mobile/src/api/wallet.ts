/**
 * Typed wrappers around the Prompt 10 wallet API.
 *
 * Read-only by design: the backend never accepts a balance or ledger write
 * from the app — money only moves through verified events.
 */
import { client } from './client';
import type {
  LedgerTransaction,
  Paginated,
  PendingEarnings,
  WalletBalance,
  WithdrawalPayload,
  WithdrawalRequest,
} from './types';

/** Current available balance + lifetime earnings/withdrawal totals. */
export async function fetchWalletBalance(): Promise<WalletBalance> {
  const { data } = await client.get<WalletBalance>('/wallet/balance/');
  return data;
}

/** Projected net of the user's sold-but-not-yet-completed items. */
export async function fetchPendingEarnings(): Promise<PendingEarnings> {
  const { data } = await client.get<PendingEarnings>('/wallet/pending-earnings/');
  return data;
}

export interface WalletTransactionFilters {
  type?: string;
  from?: string;
  to?: string;
  page?: number;
}

/** Paginated ledger history for the current user. */
export async function fetchWalletTransactions(
  filters: WalletTransactionFilters = {},
): Promise<Paginated<LedgerTransaction>> {
  const { data } = await client.get<Paginated<LedgerTransaction>>('/wallet/transactions/', {
    params: filters,
  });
  return data;
}

/** POST /api/withdrawals/ — request a payout from available balance. */
export async function requestWithdrawal(payload: WithdrawalPayload): Promise<WithdrawalRequest> {
  const { data } = await client.post<WithdrawalRequest>('/withdrawals/', payload);
  return data;
}

/** GET /api/withdrawals/ — the current user's payout requests. */
export async function fetchWithdrawals(): Promise<WithdrawalRequest[]> {
  const { data } = await client.get<WithdrawalRequest[]>('/withdrawals/');
  return data;
}
