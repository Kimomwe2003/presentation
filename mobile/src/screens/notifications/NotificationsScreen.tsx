import { useCallback, useState } from 'react';
import { FlatList, Pressable, RefreshControl, StyleSheet, Text, View } from 'react-native';

import { markAllNotificationsRead, markNotificationRead } from '../../api/notifications';
import type { AppNotification } from '../../api/types';
import EmptyState from '../../components/EmptyState';
import ErrorState from '../../components/ErrorState';
import LoadingSpinner from '../../components/LoadingSpinner';
import { useAppNotifications } from '../../hooks/useAppNotifications';
import type { RootStackParamList } from '../../navigation/types';
import { colors, radii, spacing, typography } from '../../theme';
import { formatRelativeTime } from '../../utils/format';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

type Props = NativeStackScreenProps<RootStackParamList, 'Notifications'>;

/** Deep-link a notification to its source screen based on the generic FK. */
function openNotification(navigation: Props['navigation'], item: AppNotification): void {
  switch (item.related_type) {
    case 'order':
      if (item.related_id != null) {
        navigation.navigate('OrderDetails', { orderId: item.related_id });
      }
      break;
    case 'conversation':
      if (item.related_id != null) {
        navigation.navigate('Conversation', { conversationId: item.related_id });
      }
      break;
    case 'withdrawalrequest':
      navigation.navigate('Wallet');
      break;
    default:
      break;
  }
}

export default function NotificationsScreen({ navigation }: Props) {
  const { notifications, loading, refreshing, error, refresh, reload } = useAppNotifications();
  const [readAllPending, setReadAllPending] = useState(false);

  const handlePress = useCallback(
    (item: AppNotification) => {
      if (!item.is_read) {
        void markNotificationRead(item.id).catch(() => undefined);
        item.is_read = true;
      }
      openNotification(navigation, item);
    },
    [navigation],
  );

  const handleReadAll = useCallback(() => {
    setReadAllPending(true);
    void markAllNotificationsRead()
      .catch(() => undefined)
      .finally(() => {
        setReadAllPending(false);
        void reload();
      });
  }, [reload]);

  if (loading) {
    return <LoadingSpinner label="Loading notifications…" />;
  }

  if (error && notifications.length === 0) {
    return <ErrorState message={error} onRetry={reload} />;
  }

  const unread = notifications.filter((n) => !n.is_read).length;

  return (
    <FlatList
      style={styles.list}
      contentContainerStyle={notifications.length === 0 && styles.emptyContainer}
      data={notifications}
      keyExtractor={(item) => String(item.id)}
      renderItem={({ item }) => (
        <Pressable
          onPress={() => handlePress(item)}
          style={({ pressed }) => [styles.card, pressed && styles.pressed]}
        >
          <View style={styles.row}>
            <View style={[styles.dot, item.is_read && styles.dotRead]} />
            <View style={styles.content}>
              <View style={styles.header}>
                <Text style={styles.title} numberOfLines={1}>
                  {item.title}
                </Text>
                <Text style={styles.time}>{formatRelativeTime(item.created_at)}</Text>
              </View>
              {item.body ? (
                <Text style={styles.body} numberOfLines={2}>
                  {item.body}
                </Text>
              ) : null}
            </View>
          </View>
        </Pressable>
      )}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} />}
      ListHeaderComponent={
        notifications.length > 0 ? (
          <Pressable
            onPress={handleReadAll}
            disabled={unread === 0 || readAllPending}
            style={[styles.readAll, (unread === 0 || readAllPending) && styles.readAllDisabled]}
          >
            <Text style={styles.readAllLabel}>
              {unread === 0 ? 'All caught up' : `Mark ${unread} as read`}
            </Text>
          </Pressable>
        ) : null
      }
      ListEmptyComponent={
        <EmptyState
          icon="notifications-outline"
          title="No notifications"
          message="Updates about your orders, payments and messages will appear here."
        />
      }
    />
  );
}

const styles = StyleSheet.create({
  list: {
    flex: 1,
    backgroundColor: colors.background,
  },
  emptyContainer: {
    flexGrow: 1,
    justifyContent: 'center',
  },
  readAll: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    alignItems: 'flex-end',
  },
  readAllDisabled: {
    opacity: 0.5,
  },
  readAllLabel: {
    ...typography.label,
    color: colors.primary,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    marginHorizontal: spacing.lg,
    marginTop: spacing.md,
    padding: spacing.lg,
  },
  pressed: {
    opacity: 0.85,
  },
  row: {
    flexDirection: 'row',
    gap: spacing.md,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.primary,
    marginTop: 6,
  },
  dotRead: {
    backgroundColor: colors.border,
  },
  content: {
    flex: 1,
    gap: spacing.xs,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.md,
  },
  title: {
    ...typography.body,
    fontWeight: '700',
    flexShrink: 1,
  },
  time: {
    ...typography.label,
    color: colors.textSecondary,
  },
  body: {
    ...typography.body,
    color: colors.textSecondary,
  },
});
