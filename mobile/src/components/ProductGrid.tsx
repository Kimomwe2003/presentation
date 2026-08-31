import { type ReactElement } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import type { ProductSummary } from '../api/types';
import { colors, spacing, typography } from '../theme';
import EmptyState from './EmptyState';
import ErrorState from './ErrorState';
import ProductCard from './ProductCard';
import ProductGridSkeleton from './ProductGridSkeleton';

interface ProductGridProps {
  products: ProductSummary[];
  loading: boolean;
  refreshing: boolean;
  loadingMore: boolean;
  error: string | null;
  loadMoreError: string | null;
  hasMore: boolean;
  emptyTitle: string;
  emptyMessage?: string;
  onRefresh: () => void;
  onLoadMore: () => void;
  onRetry: () => void;
  onPressProduct: (product: ProductSummary) => void;
  ListHeaderComponent?: ReactElement | null;
}

/**
 * Shared 2-column product list with skeleton, empty, error, pull-to-refresh
 * and infinite-scroll states. Home / Category / Search all render through it.
 */
export default function ProductGrid({
  products,
  loading,
  refreshing,
  loadingMore,
  error,
  loadMoreError,
  hasMore,
  emptyTitle,
  emptyMessage,
  onRefresh,
  onLoadMore,
  onRetry,
  onPressProduct,
  ListHeaderComponent,
}: ProductGridProps) {
  const showSkeleton = loading && products.length === 0;

  if (showSkeleton) {
    return (
      <View style={styles.flex}>
        {ListHeaderComponent}
        <ProductGridSkeleton />
      </View>
    );
  }

  return (
    <FlatList
      style={styles.flex}
      contentContainerStyle={[styles.content, products.length === 0 && styles.contentEmpty]}
      data={products}
      keyExtractor={(item) => String(item.id)}
      numColumns={2}
      columnWrapperStyle={products.length > 0 ? styles.columns : undefined}
      renderItem={({ item }) => (
        <View style={styles.cell}>
          <ProductCard product={item} onPress={onPressProduct} />
        </View>
      )}
      ListHeaderComponent={
        error && products.length > 0 ? (
          <View style={styles.inlineError}>
            <Text style={styles.inlineErrorText}>{error}</Text>
            <Pressable onPress={onRetry}>
              <Text style={styles.retryText}>Retry</Text>
            </Pressable>
          </View>
        ) : (
          ListHeaderComponent
        )
      }
      ListEmptyComponent={
        loading ? null : error ? (
          <ErrorState message={error} onRetry={onRetry} />
        ) : (
          <EmptyState title={emptyTitle} message={emptyMessage} />
        )
      }
      ListFooterComponent={
        <GridFooter
          hasMore={hasMore}
          loadingMore={loadingMore}
          error={loadMoreError}
          onRetry={onLoadMore}
          count={products.length}
        />
      }
      onEndReached={onLoadMore}
      onEndReachedThreshold={0.4}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />
      }
    />
  );
}

function GridFooter({
  hasMore,
  loadingMore,
  error,
  onRetry,
  count,
}: {
  hasMore: boolean;
  loadingMore: boolean;
  error: string | null;
  onRetry: () => void;
  count: number;
}) {
  if (loadingMore) {
    return (
      <View style={styles.footer}>
        <ActivityIndicator color={colors.primary} />
      </View>
    );
  }
  if (error) {
    return (
      <Pressable style={styles.footer} onPress={onRetry}>
        <Text style={styles.retryText}>{'Couldn\u0027t load more — tap to retry'}</Text>
      </Pressable>
    );
  }
  if (!hasMore && count > 0) {
    return (
      <View style={styles.footer}>
        <Text style={styles.endText}>{'You\u0027re all caught up'}</Text>
      </View>
    );
  }
  return null;
}

const styles = StyleSheet.create({
  flex: {
    flex: 1,
  },
  content: {
    padding: spacing.lg,
  },
  contentEmpty: {
    flexGrow: 1,
  },
  columns: {
    justifyContent: 'space-between',
  },
  cell: {
    width: '48%',
    marginBottom: spacing.lg,
  },
  footer: {
    paddingVertical: spacing.lg,
    alignItems: 'center',
  },
  endText: {
    ...typography.label,
  },
  inlineError: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.errorSurface,
    borderRadius: 8,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    marginBottom: spacing.md,
  },
  inlineErrorText: {
    ...typography.label,
    color: colors.error,
    flex: 1,
    marginRight: spacing.sm,
  },
  retryText: {
    color: colors.primary,
    fontWeight: '600',
    fontSize: 13,
  },
});
