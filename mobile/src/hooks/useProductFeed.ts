import { useCallback, useEffect, useRef, useState } from 'react';

import { fetchProducts, fetchProductsPage } from '../api/catalog';
import { getErrorMessage } from '../api/errors';
import type { ProductFilters, ProductSummary } from '../api/types';

export interface ProductFeedParams {
  filters?: ProductFilters;
  search?: string;
  ordering?: string;
}

export interface ProductFeedResult {
  products: ProductSummary[];
  /** Initial load / param-change load (skeleton when the list is empty). */
  loading: boolean;
  refreshing: boolean;
  loadingMore: boolean;
  error: string | null;
  loadMoreError: string | null;
  hasMore: boolean;
  refresh: () => void;
  loadMore: () => void;
  retry: () => void;
}

/**
 * Paginated, filterable product feed shared by Home / Category / Search.
 * - Param changes reload page 1 (results cleared -> skeleton).
 * - Pull-to-refresh reloads page 1 in place.
 * - Infinite scroll appends pages via the API's `next` URL.
 */
export function useProductFeed({
  filters,
  search,
  ordering,
}: ProductFeedParams = {}): ProductFeedResult {
  const [products, setProducts] = useState<ProductSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadMoreError, setLoadMoreError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);

  const nextUrlRef = useRef<string | null>(null);
  const seqRef = useRef(0);

  const paramsKey = JSON.stringify({ filters, search, ordering });

  const loadFirstPage = useCallback(
    async (mode: 'initial' | 'refresh') => {
      const seq = ++seqRef.current;
      if (mode === 'initial') {
        setLoading(true);
        setProducts([]);
      } else {
        setRefreshing(true);
      }
      setError(null);
      setLoadMoreError(null);
      try {
        const data = await fetchProducts(filters ?? {}, { search, ordering });
        if (seq !== seqRef.current) return;
        setProducts(data.results);
        nextUrlRef.current = data.next;
        setHasMore(data.next != null);
      } catch (caught) {
        if (seq !== seqRef.current) return;
        setError(getErrorMessage(caught));
      } finally {
        if (seq === seqRef.current) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    },
    [paramsKey], // eslint-disable-line react-hooks/exhaustive-deps
  );

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      // Touch state only after an await so nothing runs synchronously from the
      // effect body (react-hooks/set-state-in-effect).
      await Promise.resolve();
      if (cancelled) return;
      await loadFirstPage('initial');
    })();
    return () => {
      cancelled = true;
    };
  }, [loadFirstPage]);

  const refresh = useCallback(() => {
    void loadFirstPage('refresh');
  }, [loadFirstPage]);

  const retry = useCallback(() => {
    void loadFirstPage('initial');
  }, [loadFirstPage]);

  const loadMore = useCallback(async () => {
    if (loading || loadingMore || refreshing || !nextUrlRef.current) {
      return;
    }
    const url = nextUrlRef.current;
    const seq = seqRef.current;
    setLoadingMore(true);
    setLoadMoreError(null);
    try {
      const data = await fetchProductsPage(url);
      if (seq !== seqRef.current) return;
      setProducts((prev) => [...prev, ...data.results]);
      nextUrlRef.current = data.next;
      setHasMore(data.next != null);
    } catch (caught) {
      if (seq !== seqRef.current) return;
      setLoadMoreError(getErrorMessage(caught));
    } finally {
      if (seq === seqRef.current) {
        setLoadingMore(false);
      }
    }
  }, [loading, loadingMore, refreshing]);

  return {
    products,
    loading,
    refreshing,
    loadingMore,
    error,
    loadMoreError,
    hasMore,
    refresh,
    loadMore,
    retry,
  };
}
