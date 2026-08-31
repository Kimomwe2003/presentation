import { useCallback, useEffect, useState } from 'react';
import { FlatList, Image, Pressable, RefreshControl, StyleSheet, Text, View } from 'react-native';

import { fetchConversations } from '../../api/chat';
import { getErrorMessage } from '../../api/errors';
import type { Conversation } from '../../api/types';
import EmptyState from '../../components/EmptyState';
import ErrorState from '../../components/ErrorState';
import LoadingSpinner from '../../components/LoadingSpinner';
import type { MarketplaceScreenProps } from '../../navigation/types';
import { colors, radii, spacing, typography } from '../../theme';
import { formatRelativeTime, initials } from '../../utils/format';

type Props = MarketplaceScreenProps<'Chat'>;

export default function ConversationListScreen({ navigation }: Props) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (mode: 'initial' | 'refresh') => {
    if (mode === 'initial') {
      setLoading(true);
    } else {
      setRefreshing(true);
    }
    setError(null);
    try {
      setConversations(await fetchConversations());
    } catch (caught) {
      setError(getErrorMessage(caught));
    } finally {
      setLoading(false);
      setRefreshing(false);
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

  // Refocusing the tab (returning from a conversation) refreshes the list.
  useEffect(() => {
    const unsubscribe = navigation.addListener('focus', () => {
      void load('refresh');
    });
    return unsubscribe;
  }, [navigation, load]);

  if (loading && conversations.length === 0) {
    return <LoadingSpinner label="Loading conversations…" />;
  }

  if (error && conversations.length === 0) {
    return <ErrorState message={error} onRetry={() => void load('initial')} />;
  }

  return (
    <FlatList
      style={styles.list}
      contentContainerStyle={conversations.length === 0 ? styles.empty : undefined}
      data={conversations}
      keyExtractor={(item) => String(item.id)}
      renderItem={({ item }) => (
        <ConversationRow
          conversation={item}
          onPress={() => navigation.navigate('Conversation', { conversationId: item.id })}
        />
      )}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={() => void load('refresh')} />
      }
      ListEmptyComponent={
        <EmptyState
          icon="chatbubbles-outline"
          title="No conversations yet"
          message="Tap 'Chat with Seller' on any listing to start a conversation."
        />
      }
    />
  );
}

function ConversationRow({
  conversation,
  onPress,
}: {
  conversation: Conversation;
  onPress: () => void;
}) {
  const counterpart = conversation.counterpart;
  const name = counterpart?.full_name || counterpart?.email || 'User';
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [styles.row, pressed && styles.pressed]}
    >
      <Avatar name={name} uri={counterpart?.profile_picture ?? null} />
      <View style={styles.rowBody}>
        <View style={styles.rowTop}>
          <Text style={styles.name} numberOfLines={1}>
            {name}
          </Text>
          {conversation.last_message ? (
            <Text style={styles.time}>
              {formatRelativeTime(conversation.last_message.created_at)}
            </Text>
          ) : null}
        </View>
        <View style={styles.rowBottom}>
          <Text style={styles.preview} numberOfLines={1}>
            {conversation.last_message?.body ?? 'No messages yet'}
          </Text>
          {conversation.unread_count > 0 ? (
            <View style={styles.unreadBadge}>
              <Text style={styles.unreadText}>{conversation.unread_count}</Text>
            </View>
          ) : null}
        </View>
      </View>
    </Pressable>
  );
}

function Avatar({ name, uri }: { name: string; uri: string | null }) {
  return uri ? (
    <Image source={{ uri }} style={styles.avatar} />
  ) : (
    <View style={[styles.avatar, styles.avatarFallback]}>
      <Text style={styles.avatarText}>{initials(name)}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  list: {
    flex: 1,
    backgroundColor: colors.background,
  },
  empty: {
    flexGrow: 1,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    backgroundColor: colors.surface,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  pressed: {
    backgroundColor: '#F0F2F5',
  },
  avatar: {
    width: 48,
    height: 48,
    borderRadius: 24,
  },
  avatarFallback: {
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: {
    color: colors.onPrimary,
    fontSize: 16,
    fontWeight: '700',
  },
  rowBody: {
    flex: 1,
    gap: 4,
  },
  rowTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  name: {
    ...typography.body,
    fontWeight: '600',
  },
  time: {
    ...typography.label,
    fontSize: 12,
  },
  rowBottom: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
  },
  preview: {
    ...typography.body,
    color: colors.textSecondary,
    flex: 1,
  },
  unreadBadge: {
    backgroundColor: colors.primary,
    borderRadius: radii.round,
    minWidth: 20,
    height: 20,
    paddingHorizontal: 6,
    alignItems: 'center',
    justifyContent: 'center',
  },
  unreadText: {
    color: colors.onPrimary,
    fontSize: 12,
    fontWeight: '700',
  },
});
