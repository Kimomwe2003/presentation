import { useCallback, useEffect, useState } from 'react';
import { FlatList, Pressable, RefreshControl, StyleSheet, Text, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { fetchCart, removeCartItem, updateCartItemQuantity } from '../../api/cart';
import { getErrorMessage } from '../../api/errors';
import type { Cart, CartItem } from '../../api/types';
import Button from '../../components/Button';
import EmptyState from '../../components/EmptyState';
import ErrorState from '../../components/ErrorState';
import LoadingSpinner from '../../components/LoadingSpinner';
import { useToast } from '../../context/ToastContext';
import type { RootStackParamList } from '../../navigation/types';
import { colors, radii, spacing, typography } from '../../theme';
import { formatPrice } from '../../utils/format';

type Props = NativeStackScreenProps<RootStackParamList, 'Cart'>;

export default function CartScreen({ navigation }: Props) {
  const { showToast } = useToast();
  const [cart, setCart] = useState<Cart | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busyItem, setBusyItem] = useState<number | null>(null);
  const load = useCallback(async (mode: 'initial' | 'refresh') => {
    if (mode === 'initial') setLoading(true);
    else setRefreshing(true);
    try {
      const data = await fetchCart();
      setCart(data);
      setError(null);
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
      await Promise.resolve();
      if (cancelled) return;
      await load('initial');
    })();
    return () => {
      cancelled = true;
    };
  }, [load]);

  const changeQuantity = useCallback(
    async (item: CartItem, delta: number) => {
      const next = item.quantity + delta;
      if (next < 1) return;
      setBusyItem(item.id);
      try {
        const updated = await updateCartItemQuantity(item.id, next);
        setCart((prev) =>
          prev
            ? {
                ...prev,
                items: prev.items.map((it) => (it.id === updated.id ? updated : it)),
                item_count: Math.max(0, prev.item_count + delta),
                subtotal: (Number(prev.subtotal) + Number(updated.price) * delta).toFixed(2),
              }
            : prev,
        );
      } catch (e) {
        showToast(getErrorMessage(e));
      } finally {
        setBusyItem(null);
      }
    },
    [showToast],
  );

  const removeItem = useCallback(
    async (itemId: number) => {
      setBusyItem(itemId);
      try {
        await removeCartItem(itemId);
        setCart((prev) => {
          if (!prev) return prev;
          const removed = prev.items.find((it) => it.id === itemId);
          return {
            ...prev,
            items: prev.items.filter((it) => it.id !== itemId),
            item_count: Math.max(0, prev.item_count - (removed?.quantity ?? 1)),
            subtotal: (Number(prev.subtotal) - Number(removed?.total ?? 0)).toFixed(2),
          };
        });
        showToast('Removed from cart', { type: 'success' });
      } catch (e) {
        showToast(getErrorMessage(e));
      } finally {
        setBusyItem(null);
      }
    },
    [showToast],
  );

  const handleCheckout = useCallback(() => {
    navigation.navigate('Checkout');
  }, [navigation]);

  if (loading) {
    return <LoadingSpinner label="Loading your cart…" />;
  }

  if (error && !cart) {
    return <ErrorState message={error} onRetry={() => void load('initial')} />;
  }

  const items = cart?.items ?? [];

  return (
    <View style={styles.container}>
      <FlatList
        style={styles.list}
        data={items}
        keyExtractor={(item) => String(item.id)}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={() => void load('refresh')} />
        }
        contentContainerStyle={items.length === 0 && styles.emptyContainer}
        ListEmptyComponent={
          <EmptyState
            icon="cart-outline"
            title="Your cart is empty"
            message="Browse the marketplace and add items you’d like to buy."
            actionLabel="Browse products"
            onAction={() => navigation.navigate('Tabs', { screen: 'Home' })}
          />
        }
        renderItem={({ item }) => (
          <View style={styles.itemCard}>
            <View style={styles.itemHeader}>
              <Text style={styles.itemName} numberOfLines={1}>
                {item.product_name || `Product #${item.product_id}`}
              </Text>
              <Text style={styles.itemTotal}>{formatPrice(item.total)}</Text>
            </View>
            <Text style={styles.itemPrice}>Unit price: {formatPrice(item.price)}</Text>
            <View style={styles.itemRow}>
              <View style={styles.qtyControl}>
                <QtyButton
                  label="−"
                  disabled={item.quantity <= 1 || busyItem === item.id}
                  onPress={() => void changeQuantity(item, -1)}
                />
                <Text style={styles.qty}>{item.quantity}</Text>
                <QtyButton
                  label="+"
                  disabled={busyItem === item.id}
                  onPress={() => void changeQuantity(item, 1)}
                />
              </View>
              <Pressable
                disabled={busyItem === item.id}
                onPress={() => void removeItem(item.id)}
                style={({ pressed }) => [styles.removeBtn, pressed && styles.pressed]}
              >
                <Text style={styles.removeText}>Remove</Text>
              </Pressable>
            </View>
          </View>
        )}
      />
      {items.length > 0 ? (
        <View style={styles.footer}>
          <View style={styles.totalRow}>
            <Text style={styles.totalLabel}>Subtotal</Text>
            <Text style={styles.totalValue}>{formatPrice(cart?.subtotal ?? '0')}</Text>
          </View>
          <Button title="Checkout" onPress={handleCheckout} />
        </View>
      ) : null}
    </View>
  );
}

function QtyButton({
  label,
  onPress,
  disabled,
}: {
  label: string;
  onPress: () => void;
  disabled?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      style={({ pressed }) => [
        styles.qtyBtn,
        pressed && styles.pressed,
        disabled && styles.qtyDisabled,
      ]}
    >
      <Text style={styles.qtyBtnLabel}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  list: {
    flex: 1,
  },
  emptyContainer: {
    flexGrow: 1,
    justifyContent: 'center',
  },
  itemCard: {
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    marginHorizontal: spacing.lg,
    marginTop: spacing.md,
    padding: spacing.lg,
    gap: spacing.xs,
  },
  itemHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: spacing.md,
  },
  itemName: {
    ...typography.body,
    fontWeight: '600',
    flexShrink: 1,
  },
  itemPrice: {
    ...typography.label,
  },
  itemTotal: {
    ...typography.body,
    fontWeight: '700',
    color: colors.primary,
  },
  itemRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: spacing.sm,
  },
  qtyControl: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  qtyBtn: {
    width: 32,
    height: 32,
    borderRadius: radii.sm,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  qtyDisabled: {
    opacity: 0.4,
  },
  qtyBtnLabel: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.primary,
  },
  qty: {
    ...typography.body,
    fontWeight: '600',
    minWidth: 24,
    textAlign: 'center',
  },
  removeBtn: {
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.sm,
  },
  removeText: {
    ...typography.label,
    color: colors.error,
    fontWeight: '600',
  },
  pressed: {
    opacity: 0.7,
  },
  footer: {
    padding: spacing.lg,
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    gap: spacing.md,
  },
  totalRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  totalLabel: {
    ...typography.body,
  },
  totalValue: {
    ...typography.body,
    fontWeight: '700',
    color: colors.primary,
  },
});
