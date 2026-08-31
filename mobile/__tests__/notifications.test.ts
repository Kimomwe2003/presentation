/**
 * Unit tests for the Prompt 14 notifications API wrappers.
 */
import MockAdapter from 'axios-mock-adapter';
import * as SecureStore from 'expo-secure-store';

jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn(),
  setItemAsync: jest.fn(),
  deleteItemAsync: jest.fn(),
}));

import {
  fetchNotifications,
  fetchUnreadCount,
  markAllNotificationsRead,
  markNotificationRead,
} from '../src/api/notifications';
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

const sample = {
  id: 1,
  type: 'order_update',
  type_label: 'Order update',
  title: 'Order shipped',
  body: 'Your order is on its way.',
  is_read: false,
  related_type: 'order',
  related_id: 42,
  created_at: '2026-01-01T00:00:00Z',
};

describe('notifications API', () => {
  it('fetchNotifications returns the results array', async () => {
    mock.onGet('/notifications/').reply(200, { results: [sample], count: 1 });
    await expect(fetchNotifications()).resolves.toEqual([sample]);
  });

  it('fetchNotifications falls back to a bare array', async () => {
    mock.onGet('/notifications/').reply(200, [sample]);
    await expect(fetchNotifications()).resolves.toEqual([sample]);
  });

  it('fetchNotifications returns [] when no results key', async () => {
    mock.onGet('/notifications/').reply(200, { count: 0 });
    await expect(fetchNotifications()).resolves.toEqual([]);
  });

  it('markNotificationRead POSTs to the right URL', async () => {
    mock.onPost('/notifications/5/read/').reply(200, { ...sample, id: 5 });
    await expect(markNotificationRead(5)).resolves.toMatchObject({ id: 5 });
    expect(mock.history.post.length).toBe(1);
  });

  it('markAllNotificationsRead POSTs read-all', async () => {
    mock.onPost('/notifications/read-all/').reply(200, { marked_read: 2 });
    await expect(markAllNotificationsRead()).resolves.toBeUndefined();
    expect(mock.history.post[0].url).toBe('/notifications/read-all/');
  });

  it('fetchUnreadCount returns the numeric count', async () => {
    mock.onGet('/notifications/unread-count/').reply(200, { unread_count: 3 });
    await expect(fetchUnreadCount()).resolves.toBe(3);
  });
});
