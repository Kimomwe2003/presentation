import { useCallback, useRef, useState } from 'react';
import { FlatList, RefreshControl, StyleSheet, Text, View } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import {
  cancelOrder,
  completeItem,
  deliverItem,
  confirmItem,
  fetchOrder,
  fetchSellingOrder,
  shipItem,
} from '../../api/orders';
import { getErrorMessage } from '../../api/errors';
import type { Order, OrderAction, OrderItem } from '../../api/types';
import Button from '../../components/Button';
import Card from '../../components/Card';
import ErrorState from '../../components/ErrorState';
import LoadingSpinner from '../../components/LoadingSpinner';
import StatusBadge from '../../components/StatusBadge';
import { useToast } from '../../context/ToastContext';
import type { RootStackParamList } from '../../navigation/types';
import { colors, spacing, typography } from '../../theme';
import { formatPrice, formatRelativeTime } from '../../utils/format';

type Props = NativeStackScreenProps<RootStackParamList, 'OrderDetails'>;

const ITEM_ACTION_CALLS: Record<string, (itemId: number) => Promise<Order>> = {
  confirm: confirmItem,
  ship: shipItem,
  deliver: deliverItem,
  complete: completeItem,
};

const ORDER_ACTION_CALLS: Record<string, (id: number) => Promise<Order>> = {
  cancel: cancelOrder,
};

export default function OrderDetailsScreen({ navigation, route }: Props) {
  const { orderId, sellerView = false } = route.params;
  const { showToast } = useToast();

  const [order, setOrder] = useState<Order | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const hasLoaded = useRef(false);

  const load = useCallback(
    async (mode: 'initial' | 'refresh') => {
      if (mode === 'initial') {
        setLoading(true);
      } else {
        setRefreshing(true);
      }
      try {
        const data = sellerView ? await fetchSellingOrder(orderId) : await fetchOrder(orderId);
        setOrder(data);
        setError(null);
      } catch (e) {
        setError(getErrorMessage(e));
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [orderId, sellerView],
  );

  // Reload on every focus — including when returning from the Payment screen,
  // so a confirmed payment is reflected immediately.
  useFocusEffect(
    useCallback(() => {
      let active = true;
      void (async () => {
        // Touch state only after an await (react-hooks/set-state-in-effect).
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

  const runAction = useCallback(
    async (action: OrderAction, item?: OrderItem) => {
      const key = `${item ? `item:${item.id}:` : 'order:'}${action.action}`;
      const call = item ? ITEM_ACTION_CALLS[action.action] : ORDER_ACTION_CALLS[action.action];
      if (!call) {
        return;
      }
      setBusyAction(key);
      try {
        const updated = await call(item ? item.id : orderId);
        setOrder(updated);
        showToast(action.label + ' — done', { type: 'success' });
      } catch (e) {
        showToast(getErrorMessage(e));
      } finally {
        setBusyAction(null);
      }
    },
    [orderId, showToast],
  );

  const handlePayNow = useCallback(() => {
    navigation.navigate('Payment', { orderId });
  }, [navigation, orderId]);

  const handleReview = useCallback(
    (item: OrderItem) => {
      navigation.navigate('Review', {
        orderItemId: item.id,
        productName: item.product_name,
      });
    },
    [navigation],
  );

  if (loading && !order) {
    return <LoadingSpinner label="Loading order…" />;
  }

  if (error && !order) {
    return <ErrorState message={error} onRetry={() => void load('initial')} />;
  }

  if (!order) {
    return null;
  }

  return (
    <FlatList
      style={styles.list}
      data={order.items}
      keyExtractor={(item) => String(item.id)}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={() => void load('refresh')} />
      }
      renderItem={({ item }) => (
        <OrderItemCard item={item} buyerView={!sellerView} onReview={handleReview} />
      )}
      ListHeaderComponent={<OrderSummary order={order} />}
      ListFooterComponent={
        <OrderActions
          order={order}
          buyerView={!sellerView}
          busyAction={busyAction}
          onAction={runAction}
          onPayNow={handlePayNow}
        />
      }
    />
  );
}

function OrderSummary({ order }: { order: Order }) {
  return (
    <Card style={styles.summary}>
      <View style={styles.row}>
        <Text style={styles.orderNumber}>#{order.order_number}</Text>
        <StatusBadge status={order.status} label={order.status_label} />
      </View>
      <Text style={styles.meta}>
        Placed {formatRelativeTime(order.placed_at)} · {order.items.length} item
        {order.items.length === 1 ? '' : 's'}
      </Text>
      {order.buyer ? (
        <Text style={styles.meta}>
          Buyer: {order.buyer.full_name || order.buyer.email}
          {order.buyer.phone_number ? ` · ${order.buyer.phone_number}` : ''}
        </Text>
      ) : null}
      <View style={styles.divider} />
      <View style={styles.totalRow}>
        <Text style={styles.meta}>Subtotal</Text>
        <Text style={styles.meta}>{formatPrice(order.subtotal)}</Text>
      </View>
      <View style={styles.totalRow}>
        <Text style={styles.meta}>Shipping</Text>
        <Text style={styles.meta}>{formatPrice(order.shipping_cost)}</Text>
      </View>
      <View style={styles.totalRow}>
        <Text style={styles.totalLabel}>Total</Text>
        <Text style={styles.totalValue}>{formatPrice(order.total)}</Text>
      </View>
    </Card>
  );
}

function OrderItemCard({
  item,
  buyerView,
  onReview,
}: {
  item: OrderItem;
  buyerView: boolean;
  onReview?: (item: OrderItem) => void;
}) {
  const canReview = buyerView && item.item_status === 'completed';
  return (
    <Card style={styles.itemCard}>
      <View style={styles.row}>
        <Text style={styles.itemName}>{item.product_name}</Text>
        <StatusBadge status={item.item_status} label={item.item_status_label} />
      </View>
      <Text style={styles.meta}>
        Qty {item.quantity} × {formatPrice(item.unit_price)}
        {buyerView && item.seller ? ` · Seller: ${item.seller.full_name}` : ''}
      </Text>
      <Text style={styles.itemTotal}>{formatPrice(item.line_total)}</Text>
      {canReview && onReview ? (
        <Button
          title="Write a review"
          variant="secondary"
          onPress={() => onReview(item)}
          style={styles.reviewButton}
        />
      ) : null}
    </Card>
  );
}

function OrderActions({
  order,
  buyerView,
  busyAction,
  onAction,
  onPayNow,
}: {
  order: Order;
  buyerView: boolean;
  busyAction: string | null;
  onAction: (action: OrderAction, item?: OrderItem) => void;
  onPayNow: () => void;
}) {
  const orderActions = order.available_actions ?? [];
  const itemHasActions = order.items.some(
    (item) => item.available_actions && item.available_actions.length > 0,
  );
  const payable =
    buyerView && (order.status === 'pending_payment' || order.status === 'payment_failed');

  if (!payable && orderActions.length === 0 && !itemHasActions) {
    return null;
  }

  return (
    <View style={styles.actions}>
      {payable ? <Button title="Pay now" onPress={onPayNow} /> : null}
      {orderActions.map((action) => (
        <Button
          key={`order:${action.action}`}
          title={action.label}
          variant="danger"
          loading={busyAction === `order:${action.action}`}
          onPress={() => onAction(action)}
        />
      ))}
      {order.items.map((item) =>
        (item.available_actions ?? []).map((action) => (
          <Button
            key={`item:${item.id}:${action.action}`}
            title={`${action.label} · ${item.product_name}`}
            loading={busyAction === `item:${item.id}:${action.action}`}
            onPress={() => onAction(action, item)}
          />
        )),
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  list: {
    flex: 1,
    backgroundColor: colors.background,
  },
  summary: {
    gap: spacing.xs,
  },
  itemCard: {
    gap: spacing.xs,
  },
  row: {
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
  itemName: {
    ...typography.body,
    fontWeight: '600',
    flexShrink: 1,
  },
  meta: {
    ...typography.label,
  },
  itemTotal: {
    ...typography.body,
    fontWeight: '600',
    color: colors.primary,
  },
  reviewButton: {
    marginTop: spacing.sm,
    alignSelf: 'flex-start',
  },
  divider: {
    height: 1,
    backgroundColor: colors.border,
    marginVertical: spacing.sm,
  },
  totalRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  totalLabel: {
    ...typography.body,
    fontWeight: '700',
  },
  totalValue: {
    ...typography.body,
    fontWeight: '700',
    color: colors.primary,
  },
  actions: {
    padding: spacing.lg,
    gap: spacing.md,
  },
});
