import { useCallback, useState } from 'react';
import { FlatList, Pressable, RefreshControl, StyleSheet, Text, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { getErrorMessage } from '../../api/errors';
import { confirmItem, deliverItem, fetchSellingOrders, shipItem } from '../../api/orders';
import type { Order, OrderAction, OrderItem } from '../../api/types';
import EmptyState from '../../components/EmptyState';
import ErrorState from '../../components/ErrorState';
import LoadingSpinner from '../../components/LoadingSpinner';
import StatusBadge from '../../components/StatusBadge';
import { useToast } from '../../context/ToastContext';
import { useOrdersList } from '../../hooks/useOrdersList';
import type { RootStackParamList } from '../../navigation/types';
import { colors, radii, spacing, typography } from '../../theme';
import { formatPrice, formatRelativeTime } from '../../utils/format';

type Props = NativeStackScreenProps<RootStackParamList, 'Selling'>;

const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'pending', label: 'Pending' },
  { key: 'confirmed', label: 'Confirmed' },
  { key: 'shipped', label: 'Shipped' },
  { key: 'delivered', label: 'Delivered' },
  { key: 'completed', label: 'Completed' },
] as const;

const ITEM_ACTION_CALLS: Record<string, (itemId: number) => Promise<Order>> = {
  confirm: confirmItem,
  ship: shipItem,
  deliver: deliverItem,
};

export default function SellerOrdersScreen({ navigation }: Props) {
  const { showToast } = useToast();
  const [filter, setFilter] = useState<string>('all');
  const [busyAction, setBusyAction] = useState<string | null>(null);

  const fetcher = useCallback(
    () => fetchSellingOrders(filter === 'all' ? undefined : filter),
    [filter],
  );
  const { orders, loading, refreshing, error, refresh, reload } = useOrdersList(fetcher);

  const openOrder = useCallback(
    (order: Order) => {
      navigation.navigate('OrderDetails', { orderId: order.id, sellerView: true });
    },
    [navigation],
  );

  const runAction = useCallback(
    async (action: OrderAction, item: OrderItem) => {
      const call = ITEM_ACTION_CALLS[action.action];
      if (!call) {
        return;
      }
      const key = `item:${item.id}:${action.action}`;
      setBusyAction(key);
      try {
        await call(item.id);
        showToast(action.label + ' — done', { type: 'success' });
        // Re-pull the filtered list: the row may no longer match the chip.
        refresh();
      } catch (e) {
        showToast(getErrorMessage(e));
      } finally {
        setBusyAction(null);
      }
    },
    [refresh, showToast],
  );

  if (loading) {
    return <LoadingSpinner label="Loading incoming orders…" />;
  }

  if (error && orders.length === 0) {
    return <ErrorState message={error} onRetry={reload} />;
  }

  return (
    <FlatList
      style={styles.list}
      contentContainerStyle={orders.length === 0 && styles.emptyContainer}
      data={orders}
      keyExtractor={(item) => String(item.id)}
      renderItem={({ item }) => (
        <SellerOrderRow
          order={item}
          busyAction={busyAction}
          onPress={() => openOrder(item)}
          onAction={runAction}
        />
      )}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} />}
      ListHeaderComponent={
        <View style={styles.filters}>
          {FILTERS.map((option) => (
            <FilterChip
              key={option.key}
              label={option.label}
              selected={filter === option.key}
              onPress={() => setFilter(option.key)}
            />
          ))}
        </View>
      }
      ListEmptyComponent={
        <EmptyState
          icon="storefront-outline"
          title="Nothing to sell yet"
          message="Orders containing your listings will appear here for you to fulfil."
        />
      }
    />
  );
}

function FilterChip({
  label,
  selected,
  onPress,
}: {
  label: string;
  selected: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected }}
      onPress={onPress}
      style={({ pressed }) => [
        styles.chip,
        selected && styles.chipSelected,
        pressed && styles.pressed,
      ]}
    >
      <Text style={[styles.chipLabel, selected && styles.chipLabelSelected]}>{label}</Text>
    </Pressable>
  );
}

function SellerOrderRow({
  order,
  busyAction,
  onPress,
  onAction,
}: {
  order: Order;
  busyAction: string | null;
  onPress: () => void;
  onAction: (action: OrderAction, item: OrderItem) => void;
}) {
  const itemActions = order.items.flatMap((item) =>
    (item.available_actions ?? []).map((action) => ({ item, action })),
  );

  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.card, pressed && styles.pressed]}>
      <View style={styles.cardHeader}>
        <Text style={styles.orderNumber}>#{order.order_number}</Text>
        <StatusBadge status={order.status} label={order.status_label} />
      </View>
      <Text style={styles.meta}>
        Buyer: {order.buyer?.full_name || order.buyer?.email || 'Unknown'} ·{' '}
        {formatRelativeTime(order.placed_at)}
      </Text>
      <Text style={styles.total}>{formatPrice(order.total)}</Text>

      {itemActions.length > 0 ? (
        <View style={styles.actions}>
          {itemActions.map(({ item, action }) => {
            const key = `item:${item.id}:${action.action}`;
            return (
              <Pressable
                key={key}
                accessibilityRole="button"
                disabled={busyAction != null}
                onPress={() => onAction(action, item)}
                style={({ pressed }) => [
                  styles.quickAction,
                  busyAction === key && styles.quickActionBusy,
                  pressed && styles.pressed,
                ]}
              >
                <Text style={styles.quickActionLabel}>
                  {action.label} · {item.product_name}
                </Text>
              </Pressable>
            );
          })}
        </View>
      ) : null}
    </Pressable>
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
  filters: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
  },
  chip: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.round,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    backgroundColor: colors.surface,
  },
  chipSelected: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  chipLabel: {
    ...typography.label,
    fontSize: 13,
    fontWeight: '600',
  },
  chipLabelSelected: {
    color: colors.onPrimary,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    marginHorizontal: spacing.lg,
    marginTop: spacing.md,
    padding: spacing.lg,
    gap: spacing.xs,
  },
  pressed: {
    opacity: 0.85,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.md,
  },
  orderNumber: {
    ...typography.body,
    fontWeight: '700',
    flexShrink: 1,
  },
  meta: {
    ...typography.label,
  },
  total: {
    ...typography.body,
    fontWeight: '600',
    color: colors.primary,
  },
  actions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
    marginTop: spacing.xs,
  },
  quickAction: {
    borderWidth: 1,
    borderColor: colors.primary,
    borderRadius: radii.round,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    backgroundColor: colors.surface,
  },
  quickActionBusy: {
    opacity: 0.55,
  },
  quickActionLabel: {
    ...typography.label,
    fontSize: 12,
    fontWeight: '600',
    color: colors.primary,
  },
});
