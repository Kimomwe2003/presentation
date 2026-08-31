import { useCallback, useState } from 'react';
import { useFocusEffect } from '@react-navigation/native';

import { fetchUnreadCount } from '../api/notifications';

/**
 * Tracks the caller's unread notification count for the entry badge. Refetches
 * whenever the screen gains focus so the badge reflects recent activity.
 */
export function useUnreadNotificationCount(): number {
  const [count, setCount] = useState(0);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      void (async () => {
        await Promise.resolve();
        if (cancelled) return;
        try {
          const unread = await fetchUnreadCount();
          if (!cancelled) setCount(unread);
        } catch {
          // badge stays as-is on failure; not worth blocking the UI
        }
      })();
      return () => {
        cancelled = true;
      };
    }, []),
  );

  return count;
}
