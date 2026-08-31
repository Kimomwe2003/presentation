import { Ionicons } from '@expo/vector-icons';
import { Image, Pressable, StyleSheet, Text, View } from 'react-native';

import type { ProductSummary } from '../api/types';
import { colors, radii, spacing, typography } from '../theme';
import { CONDITION_LABELS, formatPrice, resolveImageUrl } from '../utils/format';
import FavoriteButton from './FavoriteButton';

interface ProductCardProps {
  product: ProductSummary;
  onPress: (product: ProductSummary) => void;
}

/** Shared 2-column listing card used across Home / Category / Search / Favorites. */
export default function ProductCard({ product, onPress }: ProductCardProps) {
  const imageUrl = resolveImageUrl(product.primary_image);

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={product.name}
      style={({ pressed }) => [styles.card, pressed && styles.pressed]}
      onPress={() => onPress(product)}
    >
      <View style={styles.imageWrap}>
        {imageUrl ? (
          <Image source={{ uri: imageUrl }} style={styles.image} />
        ) : (
          <View style={[styles.image, styles.imagePlaceholder]}>
            <Ionicons name="image-outline" size={32} color={colors.disabled} />
          </View>
        )}
        <View style={styles.favorite}>
          <FavoriteButton productId={product.id} />
        </View>
      </View>

      <View style={styles.body}>
        <Text numberOfLines={2} style={styles.name}>
          {product.name}
        </Text>
        <Text style={styles.price}>{formatPrice(product.price)}</Text>
        <View style={styles.metaRow}>
          <Ionicons name="location-outline" size={12} color={colors.textSecondary} />
          <Text numberOfLines={1} style={styles.meta}>
            {product.location || 'Location TBA'}
          </Text>
        </View>
        <Text style={styles.condition}>{CONDITION_LABELS[product.condition]}</Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: 'hidden',
  },
  pressed: {
    opacity: 0.85,
  },
  imageWrap: {
    aspectRatio: 1,
  },
  image: {
    width: '100%',
    height: '100%',
    backgroundColor: colors.background,
  },
  imagePlaceholder: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  favorite: {
    position: 'absolute',
    top: spacing.sm,
    right: spacing.sm,
  },
  body: {
    padding: spacing.md,
    gap: spacing.xs,
  },
  name: {
    ...typography.body,
    fontWeight: '500',
    minHeight: 38,
  },
  price: {
    ...typography.body,
    fontWeight: '700',
    fontSize: 17,
    color: colors.primary,
  },
  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
  },
  meta: {
    flex: 1,
    ...typography.label,
    fontSize: 12,
  },
  condition: {
    ...typography.label,
    fontSize: 12,
    color: colors.primary,
    fontWeight: '600',
  },
});
