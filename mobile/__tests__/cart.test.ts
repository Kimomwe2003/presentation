/**
 * Unit tests for the Prompt 18 cart + withdrawal API wrappers.
 */
import MockAdapter from 'axios-mock-adapter';
import * as SecureStore from 'expo-secure-store';

jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn(),
  setItemAsync: jest.fn(),
  deleteItemAsync: jest.fn(),
}));

import {
  addToCart,
  checkoutCart,
  fetchCart,
  removeCartItem,
  updateCartItemQuantity,
} from '../src/api/cart';
import { fetchWithdrawals, requestWithdrawal } from '../src/api/wallet';
import { client } from '../src/api/client';

let mock: MockAdapter;

beforeEach(() => {
  jest.clearAllMocks();
  (SecureStore.getItemAsync as jest.Mock).mockResolvedValue(null);
  mock = new MockAdapter(client);
});

afterEach(() => {
  mock.restore();
});

describe('cart API', () => {
  it('fetchCart gets /cart/', async () => {
    mock.onGet('/cart/').reply(200, { id: 1, item_count: 0, items: [] });
    const result = await fetchCart();
    expect(mock.history.get[0].url).toBe('/cart/');
    expect(result.id).toBe(1);
  });

  it('addToCart posts product_id and quantity', async () => {
    mock.onPost('/cart/items/').reply(201, { id: 5, product_id: 9, quantity: 1 });
    const result = await addToCart({ product_id: 9, quantity: 1 });
    expect(JSON.parse(mock.history.post[0].data)).toEqual({ product_id: 9, quantity: 1 });
    expect(result.product_id).toBe(9);
  });

  it('updateCartItemQuantity patches the quantity', async () => {
    mock.onPatch('/cart/items/3/').reply(200, { id: 3, quantity: 4 });
    const result = await updateCartItemQuantity(3, 4);
    expect(JSON.parse(mock.history.patch[0].data)).toEqual({ quantity: 4 });
    expect(result.quantity).toBe(4);
  });

  it('removeCartItem deletes /cart/items/{id}/', async () => {
    mock.onDelete('/cart/items/7/').reply(204);
    await removeCartItem(7);
    expect(mock.history.delete[0].url).toBe('/cart/items/7/');
  });

  it('checkoutCart posts to /orders/ and returns the order', async () => {
    mock.onPost('/orders/').reply(201, { id: 42, status: 'pending_payment' });
    const result = await checkoutCart({ payment_method: 'card' });
    expect(JSON.parse(mock.history.post[0].data)).toEqual({ payment_method: 'card' });
    expect(result.id).toBe(42);
  });
});

describe('withdrawal API', () => {
  it('requestWithdrawal posts payout details', async () => {
    mock.onPost('/withdrawals/').reply(201, { id: 1, status: 'pending' });
    const result = await requestWithdrawal({
      amount: '10000.00',
      provider: 'mpesa',
      mobile_money_number: '0712345678',
    });
    expect(mock.history.post[0].url).toBe('/withdrawals/');
    expect(result.status).toBe('pending');
  });

  it('fetchWithdrawals lists own requests', async () => {
    mock.onGet('/withdrawals/').reply(200, []);
    const result = await fetchWithdrawals();
    expect(mock.history.get[0].url).toBe('/withdrawals/');
    expect(result).toEqual([]);
  });
});
