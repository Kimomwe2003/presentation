/**
 * Typed Axios client for the ReuseHub backend.
 *
 * Responsibilities:
 * - Attach the JWT access token (from secure storage) to every request.
 * - On a 401, attempt a single refresh-token rotation and retry the original
 *   request once. Concurrent 401s share a single refresh call.
 * - On refresh failure, clear stored tokens and notify the auth layer so the
 *   user is routed back to Login.
 *
 * Login/register/refresh endpoints are excluded from the retry flow: a 401 on
 * those means bad credentials, not an expired session.
 */
import axios, { AxiosError, type AxiosRequestConfig } from 'axios';

import { clearTokens, getAccessToken, getRefreshToken, saveTokens } from './tokenStorage';
import type { RefreshResponse } from './types';

const API_URL = process.env.EXPO_PUBLIC_API_URL ?? 'https://presentation-g4mh.onrender.com/api';

const AUTH_ENDPOINTS = [
  '/auth/login/',
  '/auth/register/',
  '/auth/refresh/',
  '/auth/password/forgot/',
  '/auth/password/reset/',
];

// `axios.create` is the canonical factory — the rule false-positives here.
// eslint-disable-next-line import/no-named-as-default-member
export const client = axios.create({
  baseURL: API_URL,
  timeout: 45000,
  headers: {
    'Content-Type': 'application/json',
  },
});

interface RetryableConfig extends AxiosRequestConfig {
  _retry?: boolean;
}

type OnAuthExpired = () => void;

let onAuthExpired: OnAuthExpired | null = null;

/** Register a callback invoked when the session can no longer be refreshed. */
export function setOnAuthExpired(handler: OnAuthExpired): void {
  onAuthExpired = handler;
}

function isAuthEndpoint(url?: string): boolean {
  return url != null && AUTH_ENDPOINTS.some((endpoint) => url.includes(endpoint));
}

/** Single-flight refresh so concurrent 401s trigger one rotation. */
let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const refresh = await getRefreshToken();
  if (!refresh) {
    return null;
  }
  try {
    const { data } = await axios.post<RefreshResponse>(`${API_URL}/auth/refresh/`, {
      refresh,
    });
    // Rotation is enabled on the backend, but tolerate servers that only
    // return a fresh access token.
    await saveTokens(data.access, data.refresh ?? refresh);
    return data.access;
  } catch {
    await clearTokens();
    return null;
  }
}

function refreshWithDedup(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = refreshAccessToken().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

client.interceptors.request.use(async (config) => {
  if (!isAuthEndpoint(config.url)) {
    const accessToken = await getAccessToken();
    if (accessToken) {
      config.headers.Authorization = `Bearer ${accessToken}`;
    }
  }
  return config;
});

client.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as RetryableConfig | undefined;
    const status = error.response?.status;

    if (status === 401 && original && !original._retry && !isAuthEndpoint(original.url)) {
      original._retry = true;
      const newAccessToken = await refreshWithDedup();
      if (newAccessToken) {
        original.headers = original.headers ?? {};
        original.headers.Authorization = `Bearer ${newAccessToken}`;
        return client(original);
      }
      await clearTokens();
      onAuthExpired?.();
    }

    return Promise.reject(error);
  },
);
