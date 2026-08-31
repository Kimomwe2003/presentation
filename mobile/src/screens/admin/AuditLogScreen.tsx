import { useState } from 'react';
import { ActivityIndicator, FlatList, StyleSheet, Text, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { fetchAuditLogs } from '../../api/admin';
import type { AuditLogEntry, Paginated } from '../../api/types';
import TextInput from '../../components/TextInput';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import type { RootStackParamList } from '../../navigation/types';
import { colors, radii, spacing, typography } from '../../theme';

type Props = NativeStackScreenProps<RootStackParamList, 'AuditLog'>;

export default function AuditLogScreen(_props: Props) {
  const [search, setSearch] = useState('');
  const debouncedAction = useDebouncedValue(search, 300);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Paginated<AuditLogEntry> | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load(nextPage = 1, action?: string, replace = true) {
    try {
      if (replace) setLoading(true);
      else setLoadingMore(true);
      const result = await fetchAuditLogs({
        page: nextPage,
        action: action || undefined,
      });
      if (replace) setData(result);
      else
        setData((prev) =>
          prev ? { ...result, results: [...prev.results, ...result.results] } : result,
        );
      setError(null);
    } catch {
      setError('Could not load audit logs.');
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }

  // Reload when the debounced action filter changes.
  const [actionApplied, setActionApplied] = useState<string>('');
  if (actionApplied !== debouncedAction) {
    setActionApplied(debouncedAction);
    setPage(1);
    void load(1, debouncedAction, true);
  }

  function loadMore() {
    const next = page + 1;
    if (data?.next) {
      setPage(next);
      void load(next, debouncedAction, false);
    }
  }

  return (
    <View style={styles.container}>
      <TextInput
        placeholder="Filter by action (e.g. auth.login, order.transition)"
        value={search}
        onChangeText={setSearch}
        autoCapitalize="none"
      />

      {error ? <Text style={styles.error}>{error}</Text> : null}

      <FlatList
        data={data?.results ?? []}
        keyExtractor={(item) => String(item.id)}
        onEndReached={loadMore}
        onEndReachedThreshold={0.3}
        ListEmptyComponent={
          loading ? (
            <ActivityIndicator style={styles.center} color={colors.primary} />
          ) : (
            <Text style={styles.empty}>No audit entries found.</Text>
          )
        }
        ListFooterComponent={loadingMore ? <ActivityIndicator color={colors.primary} /> : null}
        renderItem={({ item }) => (
          <View style={styles.entry}>
            <View style={styles.entryHeader}>
              <Text style={styles.action}>{item.action_label}</Text>
              <Text style={styles.time}>{new Date(item.created_at).toLocaleString()}</Text>
            </View>
            <Text style={styles.description}>{item.description}</Text>
            <View style={styles.metaRow}>
              <Text style={styles.meta}>{item.actor_email ?? 'system'}</Text>
              {item.ip_address ? <Text style={styles.meta}> · {item.ip_address}</Text> : null}
              {item.target_model ? (
                <Text style={styles.meta}>
                  {' '}
                  · {item.target_model}:{item.target_id}
                </Text>
              ) : null}
            </View>
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    padding: spacing.lg,
    gap: spacing.md,
  },
  error: {
    ...typography.label,
    color: colors.error,
  },
  center: {
    marginVertical: spacing.xl,
  },
  empty: {
    ...typography.label,
    textAlign: 'center',
    marginTop: spacing.xl,
  },
  entry: {
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    padding: spacing.md,
    gap: 4,
    marginBottom: spacing.sm,
  },
  entryHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  action: {
    ...typography.body,
    fontWeight: '700',
    color: colors.primary,
  },
  time: {
    ...typography.label,
    fontSize: 11,
  },
  description: {
    ...typography.body,
    fontSize: 14,
  },
  metaRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  meta: {
    ...typography.label,
    fontSize: 11,
  },
});
