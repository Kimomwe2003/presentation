import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { fetchMessages, markConversationRead, pollNewMessages, sendMessage } from '../../api/chat';
import { getErrorMessage } from '../../api/errors';
import type { ChatMessage } from '../../api/types';
import EmptyState from '../../components/EmptyState';
import ErrorState from '../../components/ErrorState';
import LoadingSpinner from '../../components/LoadingSpinner';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import type { RootStackParamList } from '../../navigation/types';
import { colors, radii, spacing, typography } from '../../theme';
import { formatRelativeTime } from '../../utils/format';

type Props = NativeStackScreenProps<RootStackParamList, 'Conversation'>;

/** Poll the backend every N seconds while the screen is focused. */
const POLL_INTERVAL_MS = 5000;
const PAGE_SIZE = 50;

export default function ConversationScreen({ route }: Props) {
  const { conversationId } = route.params;
  const { user } = useAuth();
  const { showToast } = useToast();

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [nextPage, setNextPage] = useState<number>(2);
  const [draft, setDraft] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const listRef = useRef<FlatList<ChatMessage>>(null);
  const hasLoadedInitial = useRef(false);

  const markRead = useCallback(async () => {
    try {
      await markConversationRead(conversationId);
    } catch {
      // Best-effort; the server marks on the next successful call.
    }
  }, [conversationId]);

  const loadInitial = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const page = await fetchMessages(conversationId, { page: 1, pageSize: PAGE_SIZE });
      setMessages([...page.results].reverse());
      setHasMore(page.next != null);
      setNextPage(2);
      hasLoadedInitial.current = true;
      void markRead();
    } catch (caught) {
      setError(getErrorMessage(caught));
    } finally {
      setLoading(false);
    }
  }, [conversationId, markRead]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      await Promise.resolve();
      if (cancelled) return;
      await loadInitial();
    })();
    return () => {
      cancelled = true;
    };
  }, [loadInitial]);

  const loadOlder = useCallback(async () => {
    if (!hasMore || loadingOlder) {
      return;
    }
    setLoadingOlder(true);
    try {
      const page = await fetchMessages(conversationId, { page: nextPage, pageSize: PAGE_SIZE });
      // Older pages arrive with the newest first; align with current ascending state.
      setMessages((prev) => [...[...page.results].reverse(), ...prev]);
      setHasMore(page.next != null);
      setNextPage((n) => n + 1);
    } catch {
      // Keep what we have; pull again on next scroll event.
    } finally {
      setLoadingOlder(false);
    }
  }, [conversationId, hasMore, loadingOlder, nextPage]);

  const poll = useCallback(async () => {
    if (!hasLoadedInitial.current) {
      return;
    }
    const newestId = messages.length > 0 ? messages[messages.length - 1].id : null;
    try {
      const fresh = await pollNewMessages(conversationId, newestId);
      if (fresh.length > 0) {
        setMessages((prev) => [...prev, ...fresh]);
        void markRead();
      }
    } catch {
      // Transient network failure; next tick retries.
    }
  }, [conversationId, messages, markRead]);

  // Poll while the conversation is on screen.
  useEffect(() => {
    const timer = setInterval(() => {
      void poll();
    }, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [poll]);

  const handleSend = useCallback(async () => {
    const body = draft.trim();
    if (!body) {
      return;
    }
    setSending(true);
    try {
      const created = await sendMessage(conversationId, body);
      setMessages((prev) => [...prev, created]);
      setDraft('');
    } catch (caught) {
      showToast(getErrorMessage(caught));
    } finally {
      setSending(false);
    }
  }, [conversationId, draft, showToast]);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await loadInitial();
    } finally {
      setRefreshing(false);
    }
  }, [loadInitial]);

  if (loading) {
    return <LoadingSpinner label="Loading conversation…" />;
  }

  if (error && messages.length === 0) {
    return <ErrorState message={error} onRetry={() => void loadInitial()} />;
  }

  const myId = user?.id;

  return (
    <SafeAreaView edges={['bottom']} style={styles.safe}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={styles.flex}
      >
        <FlatList
          ref={listRef}
          style={styles.list}
          data={messages}
          keyExtractor={(item) => String(item.id)}
          renderItem={({ item }) => <MessageBubble message={item} mine={item.sender === myId} />}
          onEndReached={() => void loadOlder()}
          onEndReachedThreshold={0.4}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={() => void handleRefresh()} />
          }
          contentContainerStyle={messages.length === 0 ? styles.empty : styles.content}
          ListEmptyComponent={
            <EmptyState
              icon="chatbubble-ellipses-outline"
              title="No messages yet"
              message="Send the first message to start the conversation."
            />
          }
          ListHeaderComponent={
            loadingOlder ? (
              <View style={styles.older}>
                <ActivityIndicator color={colors.primary} />
              </View>
            ) : null
          }
        />

        <View style={styles.composer}>
          <TextInput
            style={styles.input}
            value={draft}
            onChangeText={setDraft}
            placeholder="Message…"
            placeholderTextColor={colors.textSecondary}
            multiline
            maxLength={4000}
            accessibilityLabel="Message input"
          />
          <PressableSendButton loading={sending} disabled={!draft.trim()} onPress={handleSend} />
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function MessageBubble({ message, mine }: { message: ChatMessage; mine: boolean }) {
  return (
    <View style={[styles.bubbleRow, mine ? styles.mineRow : styles.theirsRow]}>
      <View style={[styles.bubble, mine ? styles.mine : styles.theirs]}>
        <Text style={[styles.bubbleText, mine && styles.mineText]}>{message.body}</Text>
        <Text style={[styles.bubbleTime, mine && styles.mineTime]}>
          {formatRelativeTime(message.created_at)}
        </Text>
      </View>
    </View>
  );
}

function PressableSendButton({
  onPress,
  disabled,
  loading,
}: {
  onPress: () => void;
  disabled: boolean;
  loading: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel="Send message"
      onPress={onPress}
      disabled={disabled || loading}
      style={({ pressed }) => [
        styles.sendButton,
        (disabled || loading) && styles.sendDisabled,
        pressed && !disabled && styles.sendPressed,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={colors.onPrimary} />
      ) : (
        <Ionicons name="send" size={20} color={colors.onPrimary} />
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: colors.background,
  },
  flex: {
    flex: 1,
  },
  list: {
    flex: 1,
  },
  content: {
    padding: spacing.lg,
    gap: spacing.sm,
  },
  empty: {
    flexGrow: 1,
  },
  older: {
    paddingVertical: spacing.sm,
  },
  bubbleRow: {
    width: '100%',
    flexDirection: 'row',
  },
  mineRow: {
    justifyContent: 'flex-end',
  },
  theirsRow: {
    justifyContent: 'flex-start',
  },
  bubble: {
    maxWidth: '78%',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radii.md,
  },
  mine: {
    backgroundColor: colors.primary,
    borderBottomRightRadius: 4,
  },
  theirs: {
    backgroundColor: colors.surface,
    borderBottomLeftRadius: 4,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
  bubbleText: {
    ...typography.body,
    color: colors.text,
  },
  mineText: {
    color: colors.onPrimary,
  },
  bubbleTime: {
    fontSize: 11,
    color: colors.textSecondary,
    marginTop: 2,
    alignSelf: 'flex-end',
  },
  mineTime: {
    color: 'rgba(255,255,255,0.7)',
  },
  composer: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    backgroundColor: colors.surface,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
  },
  input: {
    flex: 1,
    minHeight: 40,
    maxHeight: 120,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.lg,
    paddingHorizontal: spacing.md,
    paddingTop: spacing.md,
    paddingBottom: spacing.md,
    fontSize: 15,
    color: colors.text,
    backgroundColor: colors.background,
  },
  sendButton: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sendPressed: {
    opacity: 0.85,
  },
  sendDisabled: {
    backgroundColor: colors.disabled,
  },
});
