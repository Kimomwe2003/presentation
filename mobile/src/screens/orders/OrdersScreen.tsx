import { useCallback } from 'react';
import { FlatList, Pressable, RefreshControl, StyleSheet, Text, View } from 'react-native';

import { fetchOrders } from '../../api/orders';
import type { Order } from '../../api/types';
import EmptyState from '../../components/EmptyState';
import ErrorState from '../../components/ErrorState';
import LoadingSpinner from '../../components/LoadingSpinner';
import StatusBadge from '../../components/StatusBadge';
import { useOrdersList } from '../../hooks/useOrdersList';
import type { RootStackParamList } from '../../navigation/types';
import { colors, radii, spacing, typography } from '../../theme';
import { formatPrice, formatRelativeTime } from '../../utils/format';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

type Props = NativeStackScreenProps<RootStackParamList, 'Orders'>;

function OrderRow({ order, onPress }: { order: Order; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.card, pressed && styles.pressed]}>
      <View style={styles.cardHeader}>
        <Text style={styles.orderNumber}>#{order.order_number}</Text>
        <StatusBadge status={order.status} label={order.status_label} />
      </View>
      <Text style={styles.meta}>
        {order.items.length} item{order.items.length === 1 ? '' : 's'} ·{' '}
        {formatRelativeTime(order.placed_at)}
      </Text>
      <Text style={styles.total}>{formatPrice(order.total)}</Text>
    </Pressable>
  );
}

export default function OrdersScreen({ navigation }: Props) {
  const { orders, loading, refreshing, error, refresh, reload } = useOrdersList(fetchOrders);

  const openOrder = useCallback(
    (order: Order) => {
      navigation.navigate('OrderDetails', { orderId: order.id });
    },
    [navigation],
  );

  if (loading) {
    return <LoadingSpinner label="Loading your orders…" />;
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
      renderItem={({ item }) => <OrderRow order={item} onPress={() => openOrder(item)} />}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} />}
      ListEmptyComponent={
        <EmptyState
          icon="bag-handle-outline"
          title="No orders yet"
          message="Orders you place will show up here with their status."
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
});
