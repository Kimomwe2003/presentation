/**
 * Unit tests for the Prompt 16 adminpanel API wrappers.
 */
import MockAdapter from 'axios-mock-adapter';
import * as SecureStore from 'expo-secure-store';

jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn(),
  setItemAsync: jest.fn(),
  deleteItemAsync: jest.fn(),
}));

import {
  activateUser,
  createCategory,
  fetchAdminDashboard,
  fetchAdminProducts,
  fetchAdminUserDetail,
  fetchAdminUsers,
  removeProduct,
  suspendUser,
  updateCategory,
} from '../src/api/admin';
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

describe('admin API', () => {
  it('fetchAdminDashboard gets /admin/dashboard/', async () => {
    const dashboard = {
      users: { total: 5, active: 4, suspended: 1 },
      products: { total: 10, active: 8 },
      orders_by_status: { paid: 2 },
      order_total: 2,
      transaction_value: '15000.00',
      platform_fees_collected: '900.00',
      withdrawals: { pending: 1, processing: 0, completed: 2 },
      failed_payments: 0,
      recent_activity: [],
    };
    mock.onGet('/admin/dashboard/').reply(200, dashboard);
    await expect(fetchAdminDashboard()).resolves.toEqual(dashboard);
    expect(mock.history.get[0].url).toBe('/admin/dashboard/');
  });

  it('fetchAdminUsers passes search and page params', async () => {
    mock.onGet('/admin/users/').reply(200, { count: 0, next: null, previous: null, results: [] });
    await fetchAdminUsers({ search: 'seller', page: 2 });
    expect(mock.history.get[0].params).toEqual({ search: 'seller', page: 2 });
  });

  it('fetchAdminUserDetail hits the scoped URL', async () => {
    mock.onGet('/admin/users/7/').reply(200, { id: 7 });
    await fetchAdminUserDetail(7);
    expect(mock.history.get[0].url).toBe('/admin/users/7/');
  });

  it('suspendUser posts to the suspend endpoint', async () => {
    mock.onPost('/admin/users/3/suspend/').reply(200, { id: 3, suspended: true });
    await expect(suspendUser(3)).resolves.toEqual({ id: 3, suspended: true });
  });

  it('activateUser posts to the activate endpoint', async () => {
    mock.onPost('/admin/users/3/activate/').reply(200, { id: 3, suspended: false });
    await expect(activateUser(3)).resolves.toEqual({ id: 3, suspended: false });
  });

  it('removeProduct sends the required reason', async () => {
    mock.onPost('/admin/products/5/remove/').reply(200, {
      id: 5,
      status: 'INACTIVE',
      reason: 'Scam listing',
      removed: true,
    });
    const result = await removeProduct(5, 'Scam listing');
    expect(JSON.parse(mock.history.post[0].data)).toEqual({ reason: 'Scam listing' });
    expect(result.status).toBe('INACTIVE');
  });

  it('fetchAdminProducts gets the moderation list', async () => {
    mock.onGet('/admin/products/').reply(200, { count: 0, next: null, previous: null, results: [] });
    await fetchAdminProducts();
    expect(mock.history.get[0].url).toBe('/admin/products/');
  });

  it('createAdminCategory posts the category name', async () => {
    mock.onPost('/admin/categories/').reply(201, { id: 1, name: 'Books', slug: 'books' });
    const result = await createCategory({ name: 'Books' });
    expect(JSON.parse(mock.history.post[0].data)).toEqual({ name: 'Books' });
    expect(result.slug).toBe('books');
  });

  it('updateAdminCategory patches the category', async () => {
    mock.onPatch('/admin/categories/2/').reply(200, { id: 2, is_active: false });
    const result = await updateCategory(2, { is_active: false });
    expect(result.is_active).toBe(false);
  });
});