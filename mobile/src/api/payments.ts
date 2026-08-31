/**
 * Typed wrappers around the Prompt 09 payments API (ClickPesa).
 *
 * The frontend never declares a payment successful on its own — the status
 * endpoints below only report what the backend has verified. The webhook
 * endpoint is called by ClickPesa, never by this app.
 */
import { client } from './client';
import type { PaymentState } from './types';

/** Start a ClickPesa USSD-PUSH payment attempt for the buyer's order. */
export async function initiatePayment(orderId: number, phoneNumber: string): Promise<PaymentState> {
  const { data } = await client.post<PaymentState>('/payments/initiate/', {
    order_id: orderId,
    phone_number: phoneNumber,
  });
  return data;
}

/** Latest backend-confirmed payment + order state (polling). */
export async function fetchPaymentStatus(orderId: number): Promise<PaymentState> {
  const { data } = await client.get<PaymentState>(`/payments/${orderId}/status/`);
  return data;
}

/** Manual fallback: ask the backend to re-check with ClickPesa directly. */
export async function verifyPayment(orderId: number): Promise<PaymentState> {
  const { data } = await client.post<PaymentState>(`/payments/${orderId}/verify/`);
  return data;
}
