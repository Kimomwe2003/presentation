import { useCallback, useMemo } from 'react';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import type { ProductSummary } from '../../api/types';
import ProductGrid from '../../components/ProductGrid';
import { useProductFeed } from '../../hooks/useProductFeed';
import type { RootStackParamList } from '../../navigation/types';

type Props = NativeStackScreenProps<RootStackParamList, 'Category'>;

export default function CategoryScreen({ route, navigation }: Props) {
  const { categoryId, categoryName } = route.params;

  const filters = useMemo(() => ({ category: categoryId }), [categoryId]);
  const feed = useProductFeed({ filters, ordering: '-created_at' });

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
      emptyTitle="Nothing here yet"
      emptyMessage={`No ${categoryName} listings at the moment. Check back later.`}
      onRefresh={feed.refresh}
      onLoadMore={feed.loadMore}
      onRetry={feed.retry}
      onPressProduct={openProduct}
    />
  );
}
