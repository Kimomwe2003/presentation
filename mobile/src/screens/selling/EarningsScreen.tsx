import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, RefreshControl, StyleSheet, Text, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { getErrorMessage } from '../../api/errors';
import type { LedgerTransaction } from '../../api/types';
import {
  fetchPendingEarnings,
  fetchWalletBalance,
  fetchWalletTransactions,
} from '../../api/wallet';
import Card from '../../components/Card';
import EmptyState from '../../components/EmptyState';
import ErrorState from '../../components/ErrorState';
import LoadingSpinner from '../../components/LoadingSpinner';
import TransactionRow from '../../components/TransactionRow';
import type { RootStackParamList } from '../../navigation/types';
import { colors, spacing, typography } from '../../theme';
import { formatPrice } from '../../utils/format';

type Props = NativeStackScreenProps<RootStackParamList, 'Earnings'>;

/** DRF `next` is an absolute URL like "...?page=2"; pull just the page number. */
function pageFromNext(next: string | null): number | null {
  if (!next) {
    return null;
  }
  const page = new URL(next).searchParams.get('page');
  return page ? Number(page) : null;
}

export default function EarningsScreen(_props: Props) {
  const [balance, setBalance] = useState<string>('0');
  const [pending, setPending] = useState<string>('0');
  const [totalEarnings, setTotalEarnings] = useState<string>('0');
  const [totalWithdrawn, setTotalWithdrawn] = useState<string>('0');
  const [transactions, setTransactions] = useState<LedgerTransaction[]>([]);
  const [nextPage, setNextPage] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadAll = useCallback(async (mode: 'initial' | 'refresh') => {
    if (mode === 'initial') {
      setLoading(true);
    } else {
      setRefreshing(true);
    }
    setError(null);
    try {
      const [summary, pendingData, page] = await Promise.all([
        fetchWalletBalance(),
        fetchPendingEarnings(),
        fetchWalletTransactions(),
      ]);
      setBalance(summary.balance);
      setTotalEarnings(summary.total_earnings);
      setTotalWithdrawn(summary.total_withdrawn);
      setPending(pendingData.pending_earnings);
      setTransactions(page.results);
      setNextPage(pageFromNext(page.next));
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      // Touch state only after an await so nothing runs synchronously from the
      // effect body (react-hooks/set-state-in-effect).
      await Promise.resolve();
      if (cancelled) return;
      await loadAll('initial');
    })();
    return () => {
      cancelled = true;
    };
  }, [loadAll]);

  const loadMore = useCallback(async () => {
    if (nextPage == null || loadingMore) {
      return;
    }
    setLoadingMore(true);
    try {
      const page = await fetchWalletTransactions({ page: nextPage });
      setTransactions((prev) => [...prev, ...page.results]);
      setNextPage(pageFromNext(page.next));
    } catch {
      // Keep what we have; the user can pull-to-refresh to retry.
    } finally {
      setLoadingMore(false);
    }
  }, [nextPage, loadingMore]);

  if (loading) {
    return <LoadingSpinner label="Loading your earnings…" />;
  }

  if (error && transactions.length === 0) {
    return <ErrorState message={error} onRetry={() => void loadAll('initial')} />;
  }

  return (
    <FlatList
      style={styles.list}
      contentContainerStyle={transactions.length === 0 && styles.emptyContainer}
      data={transactions}
      keyExtractor={(item) => String(item.id)}
      renderItem={({ item }) => <TransactionRow tx={item} />}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={() => void loadAll('refresh')} />
      }
      onEndReached={() => void loadMore()}
      onEndReachedThreshold={0.4}
      ListHeaderComponent={
        <View style={styles.header}>
          <Card style={styles.balanceCard}>
            <Text style={styles.balanceLabel}>Available balance</Text>
            <Text style={styles.balanceValue}>TZS {formatPrice(balance)}</Text>
          </Card>
          <Card style={styles.pendingCard}>
            <View style={styles.pendingRow}>
              <View style={styles.pendingInfo}>
                <Text style={styles.pendingLabel}>Pending earnings</Text>
                <Text style={styles.pendingHint}>
                  Items sold but not yet completed — credited to your balance as buyers confirm
                  receipt.
                </Text>
              </View>
              <Text style={styles.pendingValue}>TZS {formatPrice(pending)}</Text>
            </View>
          </Card>
          <View style={styles.statsRow}>
            <Card style={styles.stat}>
              <Text style={styles.statValue}>{formatPrice(totalEarnings)}</Text>
              <Text style={styles.statLabel}>Lifetime earnings</Text>
            </Card>
            <Card style={styles.stat}>
              <Text style={styles.statValue}>{formatPrice(totalWithdrawn)}</Text>
              <Text style={styles.statLabel}>Withdrawn</Text>
            </Card>
          </View>
          <Text style={styles.sectionTitle}>Recent activity</Text>
        </View>
      }
      ListEmptyComponent={
        <EmptyState
          icon="pricetags-outline"
          title="No activity yet"
          message="Completed sales, fees and payouts will appear here."
        />
      }
      ListFooterComponent={
        loadingMore ? (
          <View style={styles.footer}>
            <ActivityIndicator color={colors.primary} />
          </View>
        ) : null
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
  },
  header: {
    padding: spacing.lg,
    gap: spacing.md,
  },
  balanceCard: {
    alignItems: 'center',
    paddingVertical: spacing.xl,
  },
  balanceLabel: {
    ...typography.label,
  },
  balanceValue: {
    ...typography.title,
    color: colors.primary,
    marginTop: spacing.xs,
  },
  pendingCard: {
    gap: spacing.xs,
  },
  pendingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  pendingInfo: {
    flex: 1,
    gap: 2,
  },
  pendingLabel: {
    ...typography.body,
    fontWeight: '600',
  },
  pendingHint: {
    ...typography.label,
  },
  pendingValue: {
    ...typography.body,
    fontWeight: '700',
    color: colors.primary,
  },
  statsRow: {
    flexDirection: 'row',
    gap: spacing.md,
  },
  stat: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: spacing.md,
  },
  statValue: {
    ...typography.body,
    fontWeight: '700',
  },
  statLabel: {
    ...typography.label,
  },
  sectionTitle: {
    ...typography.body,
    fontWeight: '700',
    marginTop: spacing.sm,
  },
  footer: {
    paddingVertical: spacing.lg,
  },
});
