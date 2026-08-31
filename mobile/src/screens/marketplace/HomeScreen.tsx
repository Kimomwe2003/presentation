import { useCallback } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import type { Category, ProductSummary } from '../../api/types';
import CategoryChips from '../../components/CategoryChips';
import ProductGrid from '../../components/ProductGrid';
import Skeleton from '../../components/Skeleton';
import { useCategories } from '../../hooks/useCategories';
import { useProductFeed } from '../../hooks/useProductFeed';
import type { MarketplaceScreenProps } from '../../navigation/types';
import { colors, spacing, typography } from '../../theme';

type Props = MarketplaceScreenProps<'Home'>;

export default function HomeScreen({ navigation }: Props) {
  const feed = useProductFeed({ ordering: '-created_at' });
  const { categories, loading, error, reload } = useCategories();

  const handleRefresh = useCallback(() => {
    feed.refresh();
    reload();
  }, [feed, reload]);

  const openCategory = useCallback(
    (category: Category) => {
      navigation.navigate('Category', {
        categoryId: category.id,
        categoryName: category.name,
      });
    },
    [navigation],
  );

  const openProduct = useCallback(
    (product: ProductSummary) => {
      navigation.navigate('ProductDetails', {
        productId: product.id,
        productName: product.name,
      });
    },
    [navigation],
  );

  return (
    <ProductGrid
      products={feed.products}
      loading={feed.loading}
      refreshing={feed.refreshing}
      loadingMore={feed.loadingMore}
      error={feed.error}
      loadMoreError={feed.loadMoreError}
      hasMore={feed.hasMore}
      emptyTitle="No listings yet"
      emptyMessage="Be the first to post something — or check back soon."
      onRefresh={handleRefresh}
      onLoadMore={feed.loadMore}
      onRetry={feed.retry}
      onPressProduct={openProduct}
      ListHeaderComponent={
        <View style={styles.header}>
          <Text style={styles.sectionTitle}>Shop by category</Text>
          {loading ? (
            <View style={styles.chipRow}>
              <Skeleton width={96} height={34} borderRadius={17} />
              <Skeleton width={88} height={34} borderRadius={17} />
              <Skeleton width={104} height={34} borderRadius={17} />
            </View>
          ) : error ? (
            <Pressable onPress={reload} hitSlop={8}>
              <Text style={styles.retry}>{'Couldn\u0027t load categories — tap to retry'}</Text>
            </Pressable>
          ) : (
            <CategoryChips categories={categories} onSelect={openCategory} />
          )}
          <Text style={[styles.sectionTitle, styles.sectionSpacing]}>Recent listings</Text>
        </View>
      }
    />
  );
}

const styles = StyleSheet.create({
  header: {
    gap: spacing.sm,
  },
  sectionTitle: {
    ...typography.title,
    fontSize: 18,
  },
  sectionSpacing: {
    marginTop: spacing.md,
  },
  chipRow: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  retry: {
    ...typography.label,
    color: colors.primary,
    fontWeight: '600',
  },
});
