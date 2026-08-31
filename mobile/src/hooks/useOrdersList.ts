import { useCallback, useEffect, useState } from 'react';

import type { Order } from '../api/types';

interface OrdersListState {
  orders: Order[];
  loading: boolean;
  refreshing: boolean;
  error: string | null;
}

interface OrdersListResult extends OrdersListState {
  refresh: () => void;
  reload: () => void;
}

/**
 * Minimal pagination-free list state for the orders screens. Refresh pulls a
 * new page silently (pull-to-refresh); reload resets from the loading state.
 */
export function useOrdersList(fetcher: () => Promise<{ results: Order[] }>): OrdersListResult {
  const [state, setState] = useState<OrdersListState>({
    orders: [],
    loading: true,
    refreshing: false,
    error: null,
  });

  const load = useCallback(
    async (mode: 'initial' | 'refresh') => {
      setState((prev) =>
        mode === 'initial'
          ? { ...prev, loading: true, error: null }
          : { ...prev, refreshing: true, error: null },
      );
      try {
        const { results } = await fetcher();
        setState({ orders: results, loading: false, refreshing: false, error: null });
      } catch {
        setState((prev) => ({
          ...prev,
          loading: false,
          refreshing: false,
          error: 'Could not load orders. Check your connection and try again.',
        }));
      }
    },
    [fetcher],
  );

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      // Touch state only after an await so nothing runs synchronously from the
      // effect body (react-hooks/set-state-in-effect).
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
