/**
 * Typed wrappers around the Prompt 02 auth endpoints.
 *
 * The refresh call is intentionally NOT routed through `client` — it is
 * handled inside the response interceptor (see client.ts) to avoid recursion.
 */
import { client } from './client';
import type {
  AuthResponse,
  ForgotPasswordResponse,
  LoginPayload,
  RegisterPayload,
  ResetPasswordPayload,
  User,
} from './types';

export async function loginRequest(payload: LoginPayload): Promise<AuthResponse> {
  const { data } = await client.post<AuthResponse>('/auth/login/', payload);
  return data;
}

export async function registerRequest(payload: RegisterPayload): Promise<AuthResponse> {
  const { data } = await client.post<AuthResponse>('/auth/register/', payload);
  return data;
}

/** POST /api/auth/logout/ — called with a valid Bearer token; blacklists refresh. */
export async function logoutRequest(refresh: string): Promise<void> {
  await client.post('/auth/logout/', { refresh });
}

export async function fetchCurrentUser(): Promise<User> {
  const { data } = await client.get<User>('/users/me/');
  return data;
}

/** POST /api/auth/password/forgot/ — request a password-reset code. */
export async function forgotPasswordRequest(email: string): Promise<ForgotPasswordResponse> {
  const { data } = await client.post<ForgotPasswordResponse>('/auth/password/forgot/', {
    email,
  });
  return data;
}

/** POST /api/auth/password/reset/ — consume the code and set a new password. */
export async function resetPasswordRequest(payload: ResetPasswordPayload): Promise<string> {
  const { data } = await client.post<{ detail: string }>('/auth/password/reset/', payload);
  return data.detail;
}

export interface UpdateProfilePayload {
  full_name?: string;
  phone_number?: string | null;
  address?: string | null;
}

export async function updateProfile(payload: UpdateProfilePayload): Promise<User> {
  const { data } = await client.patch<User>('/users/me/', payload);
  return data;
}

export async function updateProfilePicture(uri: string): Promise<User> {
  const form = new FormData();
  form.append('profile_picture', {
    uri,
    name: `profile-${Date.now()}.jpg`,
    type: 'image/jpeg',
  } as unknown as Blob);
  const { data } = await client.patch<User>('/users/me/', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function removeProfilePicture(): Promise<User> {
  const { data } = await client.patch<User>('/users/me/', { profile_picture: null });
  return data;
}
