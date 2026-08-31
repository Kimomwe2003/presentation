/**
 * Typed wrappers around the Prompt 14 notifications API.
 *
 * The backend stores a generic FK (content_type/object_id) on each
 * notification; the serializer exposes `related_type` + `related_id` so the UI
 * can deep-link to the source object (order, conversation, wallet).
 *
 * Push delivery is deferred — see docs/ARCHITECTURE.md. The in-app list + unread
 * badge are the delivery mechanism for this prompt.
 */
import { client } from './client';
import type { AppNotification, UnreadCount } from './types';

/** The caller's notifications, newest first. */
export async function fetchNotifications(): Promise<AppNotification[]> {
  const { data } = await client.get<{ results?: AppNotification[] }>('/notifications/');
  if (Array.isArray(data)) {
    return data;
  }
  return data.results ?? [];
}

/** Mark a single notification as read. */
export async function markNotificationRead(id: number): Promise<AppNotification> {
  const { data } = await client.post<AppNotification>(`/notifications/${id}/read/`);
  return data;
}

/** Mark every notification as read. */
export async function markAllNotificationsRead(): Promise<void> {
  await client.post('/notifications/read-all/');
}

/** Current unread count, for the tab/entry badge. */
export async function fetchUnreadCount(): Promise<number> {
  const { data } = await client.get<UnreadCount>('/notifications/unread-count/');
  return data.unread_count;
}
