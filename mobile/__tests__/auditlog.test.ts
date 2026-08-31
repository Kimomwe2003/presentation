/**
 * Unit tests for the Prompt 17 audit-log and reporting API wrappers.
 */
import MockAdapter from 'axios-mock-adapter';
import * as SecureStore from 'expo-secure-store';

jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn(),
  setItemAsync: jest.fn(),
  deleteItemAsync: jest.fn(),
}));

import { fetchAdminReports, fetchAuditLogEntry, fetchAuditLogs } from '../src/api/admin';
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

describe('audit log API', () => {
  it('fetchAuditLogs gets /audit-logs/ with pagination', async () => {
    mock.onGet('/audit-logs/').reply(200, { count: 1, next: null, previous: null, results: [] });
    const result = await fetchAuditLogs({ page: 2, action: 'auth.login' });
    expect(mock.history.get[0].url).toBe('/audit-logs/');
    expect(mock.history.get[0].params).toEqual({ page: 2, action: 'auth.login' });
    expect(result.count).toBe(1);
  });

  it('fetchAuditLogEntry gets a single entry', async () => {
    mock.onGet('/audit-logs/7/').reply(200, { id: 7, action_label: 'Login' });
    const result = await fetchAuditLogEntry(7);
    expect(mock.history.get[0].url).toBe('/audit-logs/7/');
    expect(result.action_label).toBe('Login');
  });
});

describe('reports API', () => {
  it('fetchAdminReports gets /admin/reports/summary/ with days', async () => {
    mock.onGet('/admin/reports/summary/').reply(200, { days: 30, new_users: [] });
    const result = await fetchAdminReports(30);
    expect(mock.history.get[0].url).toBe('/admin/reports/summary/');
    expect(mock.history.get[0].params).toEqual({ days: 30 });
    expect(result.days).toBe(30);
  });
});
