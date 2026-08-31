/**
 * Typed wrappers around the Prompt 07 cart API + Prompt 08 checkout.
 *
 * Cart endpoints accept both anonymous (session-keyed) and authenticated
 * sessions; the client interceptor attaches the JWT when present, and the
 * backend merges the anonymous cart into the user's on login.
 */
import { client } from './client';
import type { Cart, CartItem, CartItemPayload, CheckoutPayload, Order } from './types';

/** GET /api/cart/ — the current cart (creates one if none exists). */
export async function fetchCart(): Promise<Cart> {
  const { data } = await client.get<Cart>('/cart/');
  return data;
}

/** POST /api/cart/items/ — add a product to the cart. */
export async function addToCart(payload: CartItemPayload): Promise<CartItem> {
  const { data } = await client.post<CartItem>('/cart/items/', payload);
  return data;
}

/** PATCH /api/cart/items/{id}/ — change quantity. */
export async function updateCartItemQuantity(itemId: number, quantity: number): Promise<CartItem> {
  const { data } = await client.patch<CartItem>(`/cart/items/${itemId}/`, { quantity });
  return data;
}

/** DELETE /api/cart/items/{id}/ — remove an item from the cart. */
export async function removeCartItem(itemId: number): Promise<void> {
  await client.delete(`/cart/items/${itemId}/`);
}

/** POST /api/orders/ — convert the current cart into an order. */
export async function checkoutCart(payload: CheckoutPayload): Promise<Order> {
  const { data } = await client.post<Order>('/orders/', payload);
  return data;
}
