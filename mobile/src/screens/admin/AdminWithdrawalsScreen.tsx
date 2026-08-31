import { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import {
  completeAdminWithdrawal,
  fetchAdminPendingWithdrawals,
  processAdminWithdrawal,
  rejectAdminWithdrawal,
} from '../../api/admin';
import { getErrorMessage } from '../../api/errors';
import type { WithdrawalRequest } from '../../api/types';
import Button from '../../components/Button';
import Card from '../../components/Card';
import EmptyState from '../../components/EmptyState';
import ErrorState from '../../components/ErrorState';
import StatusBadge from '../../components/StatusBadge';
import { useToast } from '../../context/ToastContext';
import type { RootStackParamList } from '../../navigation/types';
import { colors, radii, spacing, typography } from '../../theme';
import { formatPrice, formatRelativeTime } from '../../utils/format';

type Props = NativeStackScreenProps<RootStackParamList, 'AdminWithdrawals'>;

export default function AdminWithdrawalsScreen({ navigation }: Props) {
  const { showToast } = useToast();
  const [requests, setRequests] = useState<WithdrawalRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    try {
      const data = await fetchAdminPendingWithdrawals();
      setRequests(data);
      setError(null);
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );

  const handleAction = async (
    id: number,
    action: 'process' | 'complete' | 'reject',
  ) => {
    setBusyId(id);
    try {
      if (action === 'process') {
        await processAdminWithdrawal(id);
        showToast('Payout marked as processing', { type: 'success' });
      } else if (action === 'complete') {
        await completeAdminWithdrawal(id);
        showToast('Payout completed successfully', { type: 'success' });
      } else if (action === 'reject') {
        await rejectAdminWithdrawal(id);
        showToast('Payout request rejected & refunded', { type: 'success' });
      }
      await load(true);
    } catch (e) {
      showToast(getErrorMessage(e));
    } finally {
      setBusyId(null);
    }
  };

  if (loading && requests.length === 0) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  if (error && requests.length === 0) {
    return <ErrorState message={error} onRetry={() => void load()} />;
  }

  return (
    <FlatList
      style={styles.container}
      contentContainerStyle={requests.length === 0 ? styles.emptyContainer : styles.content}
      data={requests}
      keyExtractor={(item) => String(item.id)}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={() => void load(true)} />
      }
      ListHeaderComponent={
        <View style={styles.header}>
          <Text style={styles.title}>Pending Seller Payouts</Text>
          <Text style={styles.subtitle}>
            Review seller withdrawal requests and update payout lifecycle statuses.
          </Text>
        </View>
      }
      ListEmptyComponent={
        <EmptyState
          icon="wallet-outline"
          title="No pending withdrawals"
          message="All payout requests have been processed or completed."
        />
      }
      renderItem={({ item }) => (
        <Card style={styles.card}>
          <View style={styles.cardHeader}>
            <Text style={styles.amount}>{formatPrice(item.amount)}</Text>
            <StatusBadge status={item.status} label={item.status_label || item.status} />
          </View>

          <View style={styles.details}>
            <Text style={styles.meta}>
              Requested {formatRelativeTime(item.created_at)}
            </Text>
            <Text style={styles.detailText}>
              <Text style={styles.bold}>Ref:</Text> {item.reference}
            </Text>
            {item.provider_label ? (
              <Text style={styles.detailText}>
                <Text style={styles.bold}>Provider:</Text> {item.provider_label}
              </Text>
            ) : null}
            {item.mobile_money_number ? (
              <Text style={styles.detailText}>
                <Text style={styles.bold}>Phone Number:</Text> {item.mobile_money_number}
              </Text>
            ) : null}
            {item.admin_notes ? (
              <Text style={styles.detailText}>
                <Text style={styles.bold}>Notes:</Text> {item.admin_notes}
              </Text>
            ) : null}
          </View>

          <View style={styles.actions}>
            {item.status === 'pending' ? (
              <Button
                title="Process"
                variant="secondary"
                loading={busyId === item.id}
                onPress={() => void handleAction(item.id, 'process')}
                style={styles.actionBtn}
              />
            ) : null}

            {item.status === 'processing' ? (
              <Button
                title="Mark Completed"
                loading={busyId === item.id}
                onPress={() => void handleAction(item.id, 'complete')}
                style={styles.actionBtn}
              />
            ) : null}

            {item.status === 'pending' || item.status === 'processing' ? (
              <Button
                title="Reject & Refund"
                variant="danger"
                loading={busyId === item.id}
                onPress={() => void handleAction(item.id, 'reject')}
                style={styles.actionBtn}
              />
            ) : null}
          </View>
        </Card>
      )}
    />
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.lg,
    gap: spacing.md,
  },
  emptyContainer: {
    flexGrow: 1,
    padding: spacing.lg,
  },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background,
  },
  header: {
    gap: spacing.xs,
    marginBottom: spacing.sm,
  },
  title: {
    ...typography.title,
    fontSize: 20,
  },
  subtitle: {
    ...typography.label,
    color: colors.textSecondary,
  },
  card: {
    gap: spacing.md,
    marginBottom: spacing.sm,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  amount: {
    ...typography.title,
    fontSize: 20,
    color: colors.primary,
  },
  details: {
    gap: 4,
  },
  meta: {
    ...typography.label,
    fontSize: 12,
    marginBottom: spacing.xs,
  },
  detailText: {
    ...typography.body,
    fontSize: 14,
  },
  bold: {
    fontWeight: '600',
  },
  actions: {
    flexDirection: 'row',
    gap: spacing.sm,
    flexWrap: 'wrap',
    marginTop: spacing.xs,
  },
  actionBtn: {
    flex: 1,
    minWidth: 110,
  },
});
