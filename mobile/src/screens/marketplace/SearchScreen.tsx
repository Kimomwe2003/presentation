import { Ionicons } from '@expo/vector-icons';
import { useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import type { ProductFilters, ProductSummary } from '../../api/types';
import ProductGrid from '../../components/ProductGrid';
import { useCategories } from '../../hooks/useCategories';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { useProductFeed } from '../../hooks/useProductFeed';
import type { MarketplaceScreenProps } from '../../navigation/types';
import { colors, spacing } from '../../theme';
import { CONDITION_LABELS, formatPrice } from '../../utils/format';

type Props = MarketplaceScreenProps<'Search'>;

interface FilterChip {
  key: 'category' | 'condition' | 'price' | 'location';
  label: string;
}

export default function SearchScreen({ navigation, route }: Props) {
  const [query, setQuery] = useState('');
  const [filters, setFilters] = useState<ProductFilters>({});
  const debouncedQuery = useDebouncedValue(query.trim(), 400);
  const { categories } = useCategories();

  // Filters chosen in the modal arrive as tab params (see FiltersScreen).
  // Adjust state during render rather than in an effect when params change.
  const [receivedFilters, setReceivedFilters] = useState(route.params?.filters);
  if (route.params?.filters !== receivedFilters) {
    setReceivedFilters(route.params?.filters);
    if (route.params?.filters) {
      setFilters(route.params.filters);
    }
  }

  const feed = useProductFeed({
    filters,
    search: debouncedQuery || undefined,
    ordering: '-created_at',
  });

  const categoryNameById = useMemo(() => {
    const map = new Map<number, string>();
    for (const category of categories) map.set(category.id, category.name);
    return map;
  }, [categories]);

  const activeChips = useMemo<FilterChip[]>(() => {
    const chips: FilterChip[] = [];
    if (filters.category) {
      chips.push({
        key: 'category',
        label: categoryNameById.get(filters.category) ?? 'Category',
      });
    }
    if (filters.condition) {
      chips.push({ key: 'condition', label: CONDITION_LABELS[filters.condition] });
    }
    if (filters.minPrice != null || filters.maxPrice != null) {
      const min = filters.minPrice != null ? formatPrice(filters.minPrice) : '0';
      const max = filters.maxPrice != null ? formatPrice(filters.maxPrice) : 'Any';
      chips.push({ key: 'price', label: `${min} – ${max}` });
    }
    if (filters.location) {
      chips.push({ key: 'location', label: filters.location });
    }
    return chips;
  }, [filters, categoryNameById]);

  const clearChip = (key: FilterChip['key']) => {
    setFilters((prev) => {
      const next = { ...prev };
      if (key === 'category') next.category = undefined;
      if (key === 'condition') next.condition = undefined;
      if (key === 'price') {
        next.minPrice = undefined;
        next.maxPrice = undefined;
      }
      if (key === 'location') next.location = undefined;
      return next;
    });
  };

  const hasQueryOrFilters = Boolean(debouncedQuery || activeChips.length > 0);

  const header = (
    <View style={styles.header}>
      <View style={styles.searchRow}>
        <View style={styles.searchBox}>
          <Ionicons name="search" size={18} color={colors.textSecondary} />
          <TextInput
            value={query}
            onChangeText={setQuery}
            placeholder="Search ReuseHub…"
            placeholderTextColor={colors.textSecondary}
            autoCapitalize="none"
            autoCorrect={false}
            returnKeyType="search"
            style={styles.input}
          />
        </View>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Open filters"
          style={({ pressed }) => [styles.filterButton, pressed && styles.pressed]}
          onPress={() => navigation.navigate('Filters', { current: filters })}
        >
          <Ionicons name="options-outline" size={20} color={colors.text} />
        </Pressable>
      </View>

      {activeChips.length > 0 ? (
        <View style={styles.chips}>
          {activeChips.map((chip) => (
            <Pressable
              key={chip.key}
              accessibilityRole="button"
              style={({ pressed }) => [styles.chip, pressed && styles.pressed]}
              onPress={() => clearChip(chip.key)}
            >
              <Text style={styles.chipText}>{chip.label}</Text>
              <Ionicons name="close" size={14} color={colors.text} />
            </Pressable>
          ))}
          <Pressable onPress={() => setFilters({})} hitSlop={8}>
            <Text style={styles.clearAll}>Clear all</Text>
          </Pressable>
        </View>
      ) : null}
    </View>
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
      emptyTitle={hasQueryOrFilters ? 'No results' : 'Search the marketplace'}
      emptyMessage={
        hasQueryOrFilters
          ? 'Try different keywords or loosen your filters.'
          : 'Type a keyword or filter by category to find pre-loved goods.'
      }
      onRefresh={feed.refresh}
      onLoadMore={feed.loadMore}
      onRetry={feed.retry}
      onPressProduct={(product: ProductSummary) =>
        navigation.navigate('ProductDetails', {
          productId: product.id,
          productName: product.name,
        })
      }
      ListHeaderComponent={header}
    />
  );
}

const styles = StyleSheet.create({
  header: {
    gap: spacing.sm,
  },
  searchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  searchBox: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    paddingHorizontal: spacing.md,
  },
  input: {
    flex: 1,
    paddingVertical: spacing.md,
    fontSize: 15,
    color: colors.text,
  },
  filterButton: {
    width: 44,
    height: 44,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  pressed: {
    opacity: 0.7,
  },
  chips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: spacing.sm,
  },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: colors.primary,
    borderRadius: 999,
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
  },
  chipText: {
    color: colors.onPrimary,
    fontSize: 13,
    fontWeight: '600',
  },
  clearAll: {
    color: colors.primary,
    fontSize: 13,
    fontWeight: '600',
  },
});
