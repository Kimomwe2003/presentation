import { useCallback, useEffect, useState } from 'react';

import { fetchCategories } from '../api/catalog';
import type { Category } from '../api/types';

interface UseCategoriesResult {
  categories: Category[];
  loading: boolean;
  error: boolean;
  reload: () => void;
}

/** Shared category list for the Home chips, Search filter labels and Filters screen. */
export function useCategories(): UseCategoriesResult {
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      setCategories(await fetchCategories());
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      // Touch state only after an await so nothing runs synchronously from the
      // effect body (react-hooks/set-state-in-effect).
      await Promise.resolve();
      if (cancelled) return;
      await load();
    })();
    return () => {
      cancelled = true;
    };
  }, [load]);

  return { categories, loading, error, reload: load };
}
