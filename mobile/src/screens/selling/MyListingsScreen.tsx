import { useCallback } from 'react';
import { FlatList, Image, Pressable, RefreshControl, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { updateProduct } from '../../api/catalog';
import { getErrorMessage } from '../../api/errors';
import type { ProductSummary } from '../../api/types';
import Button from '../../components/Button';
import EmptyState from '../../components/EmptyState';
import ErrorState from '../../components/ErrorState';
import LoadingSpinner from '../../components/LoadingSpinner';
import StatusBadge from '../../components/StatusBadge';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { useProductFeed } from '../../hooks/useProductFeed';
import type { MarketplaceScreenProps, RootStackParamList } from '../../navigation/types';
import { colors, radii, spacing, typography } from '../../theme';
import { formatPrice, PRODUCT_STATUS_LABELS, resolveImageUrl } from '../../utils/format';

type Props = MarketplaceScreenProps<'Selling'>;

export default function MyListingsScreen({ navigation }: Props) {
  const { user } = useAuth();
  const { showToast } = useToast();

  const { products, loading, refreshing, error, hasMore, refresh, loadMore, retry } =
    useProductFeed({
      filters: { seller: user?.id },
      ordering: '-created_at',
    });

  const toggleStatus = useCallback(
    async (product: ProductSummary) => {
      const next = product.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE';
      try {
        await updateProduct(product.id, { status: next });
        showToast(next === 'ACTIVE' ? 'Listing is now live' : 'Listing deactivated', {
          type: 'success',
        });
        refresh();
      } catch (e) {
        showToast(getErrorMessage(e));
      }
    },
    [refresh, showToast],
  );

  if (loading && products.length === 0) {
    return <LoadingSpinner label="Loading your listings…" />;
  }

  if (error && products.length === 0) {
    return <ErrorState message={error} onRetry={retry} />;
  }

  return (
    <FlatList
      style={styles.list}
      contentContainerStyle={products.length === 0 && styles.emptyContainer}
      data={products}
      keyExtractor={(item) => String(item.id)}
      renderItem={({ item }) => (
        <ListingRow
          product={item}
          onView={() =>
            navigation.navigate('ProductDetails', { productId: item.id, productName: item.name })
          }
          onEdit={() => navigation.navigate('EditProduct', { productId: item.id })}
          onToggleStatus={() => void toggleStatus(item)}
        />
      )}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} />}
      onEndReached={() => void loadMore()}
      onEndReachedThreshold={0.4}
      ListHeaderComponent={
        <View style={styles.header}>
          <View style={styles.linkRow}>
            <QuickLink
              icon="storefront-outline"
              title="Incoming orders"
              subtitle="Fulfil your sales"
              onPress={() => navigation.navigate('Selling')}
            />
            <QuickLink
              icon="wallet-outline"
              title="Earnings"
              subtitle="Balance and payouts"
              onPress={() => navigation.navigate('Earnings')}
            />
          </View>
          <Button title="Add listing" onPress={() => navigation.navigate('AddProduct')} />
          <Text style={styles.sectionTitle}>My listings</Text>
        </View>
      }
      ListEmptyComponent={
        <EmptyState
          icon="pricetags-outline"
          title="No listings yet"
          message="Create your first listing to start selling on ReuseHub."
          actionLabel="Add a listing"
          onAction={() => navigation.navigate('AddProduct')}
        />
      }
      ListFooterComponent={
        hasMore ? (
          <View style={styles.footer}>
            <Text style={styles.footerText}>Pull up for more listings</Text>
          </View>
        ) : null
      }
    />
  );
}

function QuickLink({
  icon,
  title,
  subtitle,
  onPress,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  title: string;
  subtitle: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [styles.quickLink, pressed && styles.pressed]}
    >
      <Ionicons name={icon} size={22} color={colors.primary} />
      <Text style={styles.quickTitle}>{title}</Text>
      <Text style={styles.quickSubtitle}>{subtitle}</Text>
    </Pressable>
  );
}

function ListingRow({
  product,
  onView,
  onEdit,
  onToggleStatus,
}: {
  product: ProductSummary;
  onView: () => void;
  onEdit: () => void;
  onToggleStatus: () => void;
}) {
  const canToggle = product.status !== 'SOLD';
  const toggleLabel = product.status === 'ACTIVE' ? 'Deactivate' : 'Activate';
  const thumbUrl = resolveImageUrl(product.primary_image);

  return (
    <View style={styles.card}>
      <View style={styles.cardTop}>
        {thumbUrl ? (
          <Image source={{ uri: thumbUrl }} style={styles.thumb} />
        ) : (
          <View style={[styles.thumb, styles.thumbPlaceholder]}>
            <Ionicons name="image-outline" size={24} color={colors.disabled} />
          </View>
        )}
        <View style={styles.info}>
          <Text numberOfLines={2} style={styles.name}>
            {product.name}
          </Text>
          <Text style={styles.price}>{formatPrice(product.price)}</Text>
        </View>
        <StatusBadge status={product.status} label={PRODUCT_STATUS_LABELS[product.status]} />
      </View>
      <View style={styles.actions}>
        <Button
          title="View"
          variant="secondary"
          fullWidth={false}
          style={styles.actionButton}
          onPress={onView}
        />
        <Button
          title="Edit"
          variant="secondary"
          fullWidth={false}
          style={styles.actionButton}
          onPress={onEdit}
        />
        {canToggle ? (
          <Button
            title={toggleLabel}
            variant="secondary"
            fullWidth={false}
            style={styles.actionButton}
            onPress={onToggleStatus}
          />
        ) : null}
      </View>
    </View>
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
  linkRow: {
    flexDirection: 'row',
    gap: spacing.md,
  },
  quickLink: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    gap: 2,
  },
  quickTitle: {
    ...typography.body,
    fontWeight: '600',
    marginTop: spacing.xs,
  },
  quickSubtitle: {
    ...typography.label,
  },
  sectionTitle: {
    ...typography.body,
    fontWeight: '700',
    marginTop: spacing.sm,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.border,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
    padding: spacing.md,
    gap: spacing.md,
  },
  cardTop: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  thumb: {
    width: 56,
    height: 56,
    borderRadius: radii.md,
    backgroundColor: colors.background,
  },
  thumbPlaceholder: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  info: {
    flex: 1,
    gap: 2,
  },
  name: {
    ...typography.body,
    fontWeight: '600',
  },
  price: {
    ...typography.body,
    fontWeight: '700',
    color: colors.primary,
  },
  actions: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  actionButton: {
    flex: 1,
  },
  pressed: {
    opacity: 0.7,
  },
  footer: {
    paddingVertical: spacing.lg,
    alignItems: 'center',
  },
  footerText: {
    ...typography.label,
  },
});
