/**
 * Auth state manager — React Context + useReducer.
 *
 * Chosen over Redux/zustand for this project size: the only global state is
 * the session itself. Reducer gives the state transitions an explicit,
 * testable shape without adding a dependency.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  type ReactNode,
} from 'react';

import { fetchCurrentUser, loginRequest, logoutRequest, registerRequest } from '../api/auth';
import { setOnAuthExpired } from '../api/client';
import { clearTokens, getAccessToken, getRefreshToken, saveTokens } from '../api/tokenStorage';
import type { AuthResponse, LoginPayload, RegisterPayload, User } from '../api/types';

type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated';

interface AuthState {
  status: AuthStatus;
  user: User | null;
}

type AuthAction = { type: 'SESSION_START'; user: User } | { type: 'SESSION_END' };

const initialState: AuthState = {
  status: 'loading',
  user: null,
};

function reducer(state: AuthState, action: AuthAction): AuthState {
  switch (action.type) {
    case 'SESSION_START':
      return { status: 'authenticated', user: action.user };
    case 'SESSION_END':
      return { status: 'unauthenticated', user: null };
    default:
      return state;
  }
}

interface AuthContextValue extends AuthState {
  signIn: (payload: LoginPayload) => Promise<void>;
  signUp: (payload: RegisterPayload) => Promise<void>;
  signOut: () => Promise<void>;
  refetchUser: () => Promise<User | null>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/** Persist tokens and fetch the current user to complete a session start. */
async function establishSession(
  tokens: AuthResponse,
  dispatch: React.Dispatch<AuthAction>,
): Promise<User> {
  await saveTokens(tokens.access, tokens.refresh);
  try {
    const user = await fetchCurrentUser();
    dispatch({ type: 'SESSION_START', user });
    return user;
  } catch (err) {
    await clearTokens();
    throw err;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);
  // Guards against re-entrancy when the interceptor fires onAuthExpired.
  const signingOut = useRef(false);

  const signOut = useCallback(async () => {
    if (signingOut.current) {
      return;
    }
    signingOut.current = true;
    try {
      const refresh = await getRefreshToken();
      // Switch the UI to the Auth stack immediately.
      dispatch({ type: 'SESSION_END' });
      if (refresh) {
        // Best-effort server-side blacklist. Runs while tokens are still in
        // storage so the request interceptor can attach a valid Bearer header.
        try {
          await logoutRequest(refresh);
        } catch {
          // Network failure or expired session — local cleanup still happens.
        }
      }
    } finally {
      await clearTokens();
      signingOut.current = false;
    }
  }, []);

  const signIn = useCallback(async (payload: LoginPayload) => {
    const tokens = await loginRequest(payload);
    await establishSession(tokens, dispatch);
  }, []);

  const signUp = useCallback(async (payload: RegisterPayload) => {
    const tokens = await registerRequest(payload);
    await establishSession(tokens, dispatch);
  }, []);

  const refetchUser = useCallback(async () => {
    try {
      const updatedUser = await fetchCurrentUser();
      dispatch({ type: 'SESSION_START', user: updatedUser });
      return updatedUser;
    } catch {
      return null;
    }
  }, []);

  useEffect(() => {
    // On app start: only proceed if an access token exists, then validate it
    // against /users/me/. A 401 there triggers the client's refresh flow; if
    // refresh also fails, onAuthExpired fires and we end the session.
    let cancelled = false;
    (async () => {
      const accessToken = await getAccessToken();
      if (!accessToken) {
        if (!cancelled) dispatch({ type: 'SESSION_END' });
        return;
      }
      try {
        const user = await fetchCurrentUser();
        if (!cancelled) dispatch({ type: 'SESSION_START', user });
      } catch {
        // Tokens were cleared by the interceptor on refresh failure.
        if (!cancelled) dispatch({ type: 'SESSION_END' });
      }
    })();

    setOnAuthExpired(() => {
      void signOut();
    });

    return () => {
      cancelled = true;
    };
  }, [signOut]);

  const value = useMemo<AuthContextValue>(
    () => ({ ...state, signIn, signUp, signOut, refetchUser }),
    [state, signIn, signUp, signOut, refetchUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
