/**
 * Typed wrappers around the Prompt 08 orders API.
 *
 * Every endpoint requires an authenticated session. Action calls (cancel,
 * confirm, ship, deliver, complete) return the updated order so callers can
 * refresh in place.
 */
import { client } from './client';
import type { Order, Paginated } from './types';

/** Buyer's own orders. */
export async function fetchOrders(): Promise<Paginated<Order>> {
  const { data } = await client.get<Paginated<Order>>('/orders/');
  return data;
}

/** Buyer's order detail. */
export async function fetchOrder(id: number): Promise<Order> {
  const { data } = await client.get<Order>(`/orders/${id}/`);
  return data;
}

/** Orders containing the current user's items (seller's inbox). */
export async function fetchSellingOrders(itemStatus?: string): Promise<Paginated<Order>> {
  const { data } = await client.get<Paginated<Order>>('/orders/selling/', {
    params: itemStatus ? { item_status: itemStatus } : undefined,
  });
  return data;
}

/** Seller's view of a single order (only their items are returned). */
export async function fetchSellingOrder(id: number): Promise<Order> {
  const { data } = await client.get<Order>(`/orders/selling/${id}/`);
  return data;
}

export async function cancelOrder(id: number): Promise<Order> {
  const { data } = await client.post<Order>(`/orders/${id}/cancel/`);
  return data;
}

export async function confirmItem(itemId: number): Promise<Order> {
  const { data } = await client.post<Order>(`/orders/items/${itemId}/confirm/`);
  return data;
}

export async function shipItem(itemId: number): Promise<Order> {
  const { data } = await client.post<Order>(`/orders/items/${itemId}/ship/`);
  return data;
}

export async function deliverItem(itemId: number): Promise<Order> {
  const { data } = await client.post<Order>(`/orders/items/${itemId}/deliver/`);
  return data;
}

export async function completeItem(itemId: number): Promise<Order> {
  const { data } = await client.post<Order>(`/orders/items/${itemId}/complete/`);
  return data;
}
