/**
 * Unit tests for the Axios refresh-on-401 retry logic (mocked HTTP layer).
 */
import axios from 'axios';
import MockAdapter from 'axios-mock-adapter';
import * as SecureStore from 'expo-secure-store';

jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn(),
  setItemAsync: jest.fn(),
  deleteItemAsync: jest.fn(),
}));

import { client, setOnAuthExpired } from '../src/api/client';

const ACCESS_KEY = 'reusehub.access_token';
const REFRESH_KEY = 'reusehub.refresh_token';

let accessToken: string | null;
let refreshToken: string | null;

const mockGetItem = SecureStore.getItemAsync as jest.Mock;
const mockSetItem = SecureStore.setItemAsync as jest.Mock;
const mockDeleteItem = SecureStore.deleteItemAsync as jest.Mock;

let mockClient: MockAdapter;
let mockRefresh: MockAdapter;

beforeEach(() => {
  accessToken = null;
  refreshToken = null;
  jest.clearAllMocks();

  mockGetItem.mockImplementation((key: string) =>
    Promise.resolve(key === ACCESS_KEY ? accessToken : key === REFRESH_KEY ? refreshToken : null),
  );
  mockSetItem.mockResolvedValue(undefined);
  mockDeleteItem.mockResolvedValue(undefined);

  mockClient = new MockAdapter(client);
  mockRefresh = new MockAdapter(axios);
});

afterEach(() => {
  mockClient.restore();
  mockRefresh.restore();
});

describe('request interceptor', () => {
  it('attaches the stored access token as a Bearer header', async () => {
    accessToken = 'stored-access';
    mockClient.onGet(/\/api\/data$/).reply((config) => {
      expect(config.headers?.Authorization).toBe('Bearer stored-access');
      return [200, { ok: true }];
    });

    const response = await client.get('/data');
    expect(response.data).toEqual({ ok: true });
    expect(mockClient.history.get).toHaveLength(1);
  });

  it('sends unauthenticated requests without an Authorization header', async () => {
    mockClient.onGet(/\/api\/public$/).reply((config) => {
      expect(config.headers?.Authorization).toBeUndefined();
      return [200, { ok: true }];
    });

    await client.get('/public');
  });
});

describe('401 refresh-retry flow', () => {
  it('refreshes once on a 401 and retries the original request with the new token', async () => {
    accessToken = 'expired-access';
    refreshToken = 'good-refresh';
    const onAuthExpired = jest.fn();
    setOnAuthExpired(onAuthExpired);

    let calls = 0;
    mockClient.onGet(/\/api\/data$/).reply(() => {
      calls += 1;
      if (calls === 1) {
        return [401, { detail: 'Given token not valid' }];
      }
      expect((client.defaults.headers as Record<string, unknown>)['Authorization']).toBeUndefined();
      return [200, { ok: true }];
    });
    mockRefresh.onPost(/\/auth\/refresh\//).reply(200, {
      access: 'fresh-access',
      refresh: 'rotated-refresh',
    });

    const response = await client.get('/data');

    expect(response.data).toEqual({ ok: true });
    expect(calls).toBe(2);
    expect(mockRefresh.history.post).toHaveLength(1);
    expect(mockRefresh.history.post[0].data).toBe(JSON.stringify({ refresh: 'good-refresh' }));
    expect(mockSetItem).toHaveBeenCalledWith(ACCESS_KEY, 'fresh-access');
    expect(mockSetItem).toHaveBeenCalledWith(REFRESH_KEY, 'rotated-refresh');
    expect(onAuthExpired).not.toHaveBeenCalled();
  });

  it('rejects the request and ends the session when no refresh token exists', async () => {
    accessToken = 'expired-access';
    refreshToken = null;
    const onAuthExpired = jest.fn();
    setOnAuthExpired(onAuthExpired);

    mockClient.onGet(/\/api\/data$/).reply(401, { detail: 'Given token not valid' });

    await expect(client.get('/data')).rejects.toMatchObject({ response: { status: 401 } });
    expect(mockRefresh.history.post).toHaveLength(0);
    expect(mockDeleteItem).toHaveBeenCalledWith(ACCESS_KEY);
    expect(mockDeleteItem).toHaveBeenCalledWith(REFRESH_KEY);
    expect(onAuthExpired).toHaveBeenCalledTimes(1);
  });

  it('rejects the request and ends the session when refresh fails', async () => {
    accessToken = 'expired-access';
    refreshToken = 'revoked-refresh';
    const onAuthExpired = jest.fn();
    setOnAuthExpired(onAuthExpired);

    mockClient.onGet(/\/api\/data$/).reply(401, { detail: 'Given token not valid' });
    mockRefresh.onPost(/\/auth\/refresh\//).reply(401, { detail: 'Token is invalid or expired' });

    await expect(client.get('/data')).rejects.toMatchObject({ response: { status: 401 } });
    expect(mockRefresh.history.post).toHaveLength(1);
    expect(mockDeleteItem).toHaveBeenCalledWith(ACCESS_KEY);
    expect(onAuthExpired).toHaveBeenCalledTimes(1);
  });

  it('does not retry when the retried request itself returns 401', async () => {
    accessToken = 'expired-access';
    refreshToken = 'good-refresh';
    const onAuthExpired = jest.fn();
    setOnAuthExpired(onAuthExpired);

    mockClient.onGet(/\/api\/data$/).reply(401, { detail: 'Given token not valid' });
    mockRefresh.onPost(/\/auth\/refresh\//).reply(200, { access: 'fresh-access' });

    await expect(client.get('/data')).rejects.toBeDefined();
    // One refresh attempt; the retried request must NOT trigger a second one.
    expect(mockRefresh.history.post).toHaveLength(1);
    expect(onAuthExpired).not.toHaveBeenCalled();
  });

  it('shares a single refresh call across concurrent 401s', async () => {
    accessToken = 'expired-access';
    refreshToken = 'good-refresh';

    const aHandlers = [401, 200];
    const bHandlers = [401, 200];
    mockClient.onGet(/\/api\/a$/).reply(() => [aHandlers.shift()!, { ok: true }]);
    mockClient.onGet(/\/api\/b$/).reply(() => [bHandlers.shift()!, { ok: true }]);
    mockRefresh.onPost(/\/auth\/refresh\//).reply(200, { access: 'fresh-access' });

    const [a, b] = await Promise.all([client.get('/a'), client.get('/b')]);

    expect(a.status).toBe(200);
    expect(b.status).toBe(200);
    expect(mockRefresh.history.post).toHaveLength(1);
  });
});

describe('auth endpoints are excluded from the retry flow', () => {
  it('does not attempt refresh when login returns 401', async () => {
    accessToken = 'stale-token';
    refreshToken = 'stale-refresh';
    const onAuthExpired = jest.fn();
    setOnAuthExpired(onAuthExpired);

    mockClient.onPost(/\/auth\/login\//).reply(401, { detail: 'Unable to log in.' });

    await expect(
      client.post('/auth/login/', { email: 'a@b.c', password: 'x' }),
    ).rejects.toMatchObject({
      response: { status: 401 },
    });
    expect(mockRefresh.history.post).toHaveLength(0);
    expect(mockDeleteItem).not.toHaveBeenCalled();
    expect(onAuthExpired).not.toHaveBeenCalled();
  });
});
