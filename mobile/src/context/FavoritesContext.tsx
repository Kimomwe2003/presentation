/**
 * Favorites state — single source of truth for the favorite heart across
 * ProductCard / ProductDetails. Loaded from the backend on mount (so the
 * state survives app restarts), then updated optimistically on toggle with
 * rollback on failure.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import { addFavorite, fetchFavorites, removeFavorite } from '../api/catalog';
import { useAuth } from './AuthContext';
import { useToast } from './ToastContext';

interface FavoritesContextValue {
  /** Product ids currently favorited by the user. */
  favoriteIds: ReadonlySet<number>;
  loading: boolean;
  isFavorite: (productId: number) => boolean;
  toggleFavorite: (productId: number) => Promise<void>;
}

const FavoritesContext = createContext<FavoritesContextValue | null>(null);

export function FavoritesProvider({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const { showToast } = useToast();
  const [favoriteIds, setFavoriteIds] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(true);

  const authenticated = status === 'authenticated';

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      // Touch state only after an await so nothing runs synchronously from the
      // effect body (react-hooks/set-state-in-effect).
      await Promise.resolve();
      if (cancelled) return;
      if (!authenticated) {
        setFavoriteIds(new Set());
        setLoading(false);
        return;
      }
      setLoading(true);
      try {
        const favorites = await fetchFavorites();
        if (!cancelled) {
          setFavoriteIds(new Set(favorites.map((f) => f.product.id)));
        }
      } catch {
        // Favorites are non-critical; leave the set empty rather than blocking.
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [authenticated]);

  const isFavorite = useCallback((productId: number) => favoriteIds.has(productId), [favoriteIds]);

  const toggleFavorite = useCallback(
    async (productId: number) => {
      const wasFavorite = favoriteIds.has(productId);
      // Optimistic update.
      setFavoriteIds((prev) => {
        const next = new Set(prev);
        if (wasFavorite) {
          next.delete(productId);
        } else {
          next.add(productId);
        }
        return next;
      });
      try {
        if (wasFavorite) {
          await removeFavorite(productId);
        } else {
          await addFavorite(productId);
        }
      } catch {
        // Roll back on failure.
        setFavoriteIds((prev) => {
          const next = new Set(prev);
          if (wasFavorite) {
            next.add(productId);
          } else {
            next.delete(productId);
          }
          return next;
        });
        showToast(wasFavorite ? "Couldn't remove from favorites." : "Couldn't add to favorites.", {
          type: 'error',
        });
      }
    },
    [favoriteIds, showToast],
  );

  const value = useMemo<FavoritesContextValue>(
    () => ({ favoriteIds, loading, isFavorite, toggleFavorite }),
    [favoriteIds, loading, isFavorite, toggleFavorite],
  );

  return <FavoritesContext.Provider value={value}>{children}</FavoritesContext.Provider>;
}

export function useFavorites(): FavoritesContextValue {
  const context = useContext(FavoritesContext);
  if (!context) {
    throw new Error('useFavorites must be used within a FavoritesProvider');
  }
  return context;
}
