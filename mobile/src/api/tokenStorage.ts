/**
 * Token storage backed by expo-secure-store.
 *
 * Only authentication tokens live here — nothing else. The keychain-backed
 * store (iOS) / Keystore (Android) is used instead of AsyncStorage because
 * tokens are secrets that must not sit in plaintext.
 */
import * as SecureStore from 'expo-secure-store';

const ACCESS_TOKEN_KEY = 'reusehub.access_token';
const REFRESH_TOKEN_KEY = 'reusehub.refresh_token';

export async function getAccessToken(): Promise<string | null> {
  return SecureStore.getItemAsync(ACCESS_TOKEN_KEY);
}

export async function getRefreshToken(): Promise<string | null> {
  return SecureStore.getItemAsync(REFRESH_TOKEN_KEY);
}

export async function saveTokens(access: string, refresh?: string): Promise<void> {
  await SecureStore.setItemAsync(ACCESS_TOKEN_KEY, access);
  if (refresh !== undefined) {
    await SecureStore.setItemAsync(REFRESH_TOKEN_KEY, refresh);
  }
}

export async function clearTokens(): Promise<void> {
  await Promise.all([
    SecureStore.deleteItemAsync(ACCESS_TOKEN_KEY),
    SecureStore.deleteItemAsync(REFRESH_TOKEN_KEY),
  ]);
}
