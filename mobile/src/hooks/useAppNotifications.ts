import { useCallback, useEffect, useState } from 'react';

import { fetchNotifications } from '../api/notifications';
import type { AppNotification } from '../api/types';

interface NotificationsState {
  notifications: AppNotification[];
  loading: boolean;
  refreshing: boolean;
  error: string | null;
}

interface NotificationsResult extends NotificationsState {
  refresh: () => void;
  reload: () => void;
}

/**
 * List state for the notifications screen (Prompt 14). Mirrors useOrdersList:
 * pull-to-refresh fetches silently; reload resets from the loading state.
 */
export function useAppNotifications(): NotificationsResult {
  const [state, setState] = useState<NotificationsState>({
    notifications: [],
    loading: true,
    refreshing: false,
    error: null,
  });

  const load = useCallback(async (mode: 'initial' | 'refresh') => {
    setState((prev) =>
      mode === 'initial'
        ? { ...prev, loading: true, error: null }
        : { ...prev, refreshing: true, error: null },
    );
    try {
      const notifications = await fetchNotifications();
      setState({ notifications, loading: false, refreshing: false, error: null });
    } catch {
      setState((prev) => ({
        ...prev,
        loading: false,
        refreshing: false,
        error: 'Could not load notifications. Check your connection and try again.',
      }));
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      await Promise.resolve();
      if (cancelled) return;
      await load('initial');
    })();
    return () => {
      cancelled = true;
    };
  }, [load]);

  const refresh = useCallback(() => {
    void load('refresh');
  }, [load]);

  const reload = useCallback(() => {
    void load('initial');
  }, [load]);

  return { ...state, refresh, reload };
}
