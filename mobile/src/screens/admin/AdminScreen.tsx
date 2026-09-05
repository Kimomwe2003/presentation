import { useCallback, useRef, useState } from 'react';
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';

import { fetchAdminDashboard } from '../../api/admin';
import type { AdminDashboard } from '../../api/types';
import { useAuth } from '../../context/AuthContext';
import Button from '../../components/Button';
import Card from '../../components/Card';
import type { MarketplaceScreenProps } from '../../navigation/types';
import { colors, spacing, typography } from '../../theme';

type Props = MarketplaceScreenProps<'Admin'>;

export default function AdminScreen({ navigation }: Props) {
  const { user, signOut } = useAuth();
  const [data, setData] = useState<AdminDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const hasLoaded = useRef(false);

  const load = useCallback(async (mode: 'initial' | 'refresh') => {
    if (mode === 'refresh') setRefreshing(true);
    try {
      const dashboard = await fetchAdminDashboard();
      setData(dashboard);
      setError(null);
    } catch {
      if (!hasLoaded.current) setError('Could not load the dashboard.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  // Reload on every focus so earnings/stats stay fresh.
  useFocusEffect(
    useCallback(() => {
      let active = true;
      void (async () => {
        await Promise.resolve();
        if (active) {
          await load(hasLoaded.current ? 'refresh' : 'initial');
          hasLoaded.current = true;
        }
      })();
      return () => {
        active = false;
      };
    }, [load]),
  );

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  if (error || !data) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>{error ?? 'Nothing to show.'}</Text>
        <Button title="Retry" onPress={() => void load('initial')} />
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void load('refresh')} />}
    >
      <Text style={styles.subtitle}>Signed in as {user?.email} — administrator</Text>

      <View style={styles.grid}>
        <StatCard
          label="Users"
          value={data.users.total}
          detail={`${data.users.active} active · ${data.users.suspended} suspended`}
        />
        <StatCard
          label="Products"
          value={data.products.total}
          detail={`${data.products.active} active`}
        />
        <StatCard label="Orders" value={data.order_total} />
        <StatCard
          label="Platform fees"
          value={`TZS ${Number(data.platform_fees_collected).toLocaleString()}`}
        />
        <StatCard
          label="Transaction value"
          value={`TZS ${Number(data.transaction_value).toLocaleString()}`}
        />
        <StatCard
          label="Pending withdrawals"
          value={data.withdrawals.pending}
          detail={`${data.withdrawals.processing} processing · ${data.withdrawals.completed} completed`}
          onPress={() => navigation.navigate('AdminWithdrawals')}
        />
      </View>

      <Card style={styles.actions}>
        <Text style={styles.sectionTitle}>Moderation</Text>
        <Pressable
          onPress={() => navigation.navigate('AdminUsers')}
          style={({ pressed }) => [styles.row, pressed && styles.pressed]}
        >
          <Text style={styles.rowLabel}>Manage users</Text>
          <Text style={styles.rowHint}>Search, suspend and reactivate accounts</Text>
        </Pressable>
        <View style={styles.separator} />
        <Pressable
          onPress={() => navigation.navigate('AdminProducts')}
          style={({ pressed }) => [styles.row, pressed && styles.pressed]}
        >
          <Text style={styles.rowLabel}>Moderate products</Text>
          <Text style={styles.rowHint}>Review and remove listings</Text>
        </Pressable>
        <View style={styles.separator} />
        <Pressable
          onPress={() => navigation.navigate('AdminWithdrawals')}
          style={({ pressed }) => [styles.row, pressed && styles.pressed]}
        >
          <Text style={styles.rowLabel}>Withdrawal approvals</Text>
          <Text style={styles.rowHint}>Review and process seller payout requests</Text>
        </Pressable>
      </Card>

      <Card style={styles.actions}>
        <Text style={styles.sectionTitle}>Security & insights</Text>
        <Pressable
          onPress={() => navigation.navigate('AuditLog')}
          style={({ pressed }) => [styles.row, pressed && styles.pressed]}
        >
          <Text style={styles.rowLabel}>Audit log</Text>
          <Text style={styles.rowHint}>Append-only record of sensitive actions</Text>
        </Pressable>
        <View style={styles.separator} />
        <Pressable
          onPress={() => navigation.navigate('Reports')}
          style={({ pressed }) => [styles.row, pressed && styles.pressed]}
        >
          <Text style={styles.rowLabel}>Reports</Text>
          <Text style={styles.rowHint}>Transaction volume, fees and new users</Text>
        </Pressable>
      </Card>

      <Card style={styles.activity}>
        <Text style={styles.sectionTitle}>Recent activity</Text>
        {data.recent_activity.map((activity) => (
          <View key={`${activity.type}-${activity.created_at}`} style={styles.activityRow}>
            <Text style={styles.activityMessage}>{activity.message}</Text>
            <Text style={styles.activityTime}>
              {new Date(activity.created_at).toLocaleDateString()}
            </Text>
          </View>
        ))}
        {data.recent_activity.length === 0 ? (
          <Text style={styles.empty}>No activity yet.</Text>
        ) : null}
      </Card>

      <Button title="Log out" variant="danger" onPress={() => void signOut()} />
    </ScrollView>
  );
}

function StatCard({
  label,
  value,
  detail,
  onPress,
}: {
  label: string;
  value: string | number;
  detail?: string;
  onPress?: () => void;
}) {
  const content = (
    <Card style={styles.statCard}>
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
      {detail ? <Text style={styles.statDetail}>{detail}</Text> : null}
    </Card>
  );

  if (onPress) {
    return (
      <Pressable
        onPress={onPress}
        style={({ pressed }) => [styles.statCardContainer, pressed && styles.pressed]}
      >
        {content}
      </Pressable>
    );
  }

  return content;
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.lg,
    gap: spacing.lg,
  },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background,
    gap: spacing.lg,
    padding: spacing.lg,
  },
  errorText: {
    ...typography.body,
    color: colors.error,
    textAlign: 'center',
  },
  subtitle: {
    ...typography.label,
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.md,
  },
  statCard: {
    flex: 1,
    gap: spacing.xs,
  },
  statCardContainer: {
    flexBasis: '47%',
    flexGrow: 1,
  },
  statValue: {
    ...typography.title,
    fontSize: 22,
    color: colors.primary,
  },
  statLabel: {
    ...typography.label,
  },
  statDetail: {
    ...typography.label,
    color: colors.textSecondary,
    fontSize: 11,
  },
  actions: {
    gap: spacing.md,
  },
  sectionTitle: {
    ...typography.subtitle,
    fontWeight: '700',
  },
  row: {
    gap: 2,
  },
  rowLabel: {
    ...typography.body,
    fontWeight: '600',
  },
  rowHint: {
    ...typography.label,
  },
  pressed: {
    opacity: 0.7,
  },
  separator: {
    height: 1,
    backgroundColor: colors.border,
  },
  activity: {
    gap: spacing.md,
  },
  activityRow: {
    gap: 2,
  },
  activityMessage: {
    ...typography.body,
    fontSize: 14,
  },
  activityTime: {
    ...typography.label,
    fontSize: 11,
  },
  empty: {
    ...typography.label,
  },
});
