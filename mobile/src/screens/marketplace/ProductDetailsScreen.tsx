import { Ionicons } from '@expo/vector-icons';
import { useCallback, useEffect, useState } from 'react';
import { Image, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { fetchProduct } from '../../api/catalog';
import { addToCart } from '../../api/cart';
import { fetchProductReviews } from '../../api/reviews';
import { openConversationForProduct } from '../../api/chat';
import { getErrorMessage } from '../../api/errors';
import type { ProductDetail, Review } from '../../api/types';
import Button from '../../components/Button';
import ErrorState from '../../components/ErrorState';
import FavoriteButton from '../../components/FavoriteButton';
import ImageCarousel from '../../components/ImageCarousel';
import LoadingSpinner from '../../components/LoadingSpinner';
import RatingStars from '../../components/RatingStars';
import ReviewItem from '../../components/ReviewItem';
import { useToast } from '../../context/ToastContext';
import type { RootStackParamList } from '../../navigation/types';
import { colors, radii, spacing, typography } from '../../theme';
import { CONDITION_LABELS, formatPrice, formatRelativeTime, initials, resolveImageUrl } from '../../utils/format';

type Props = NativeStackScreenProps<RootStackParamList, 'ProductDetails'>;

export default function ProductDetailsScreen({ route, navigation }: Props) {
  const { productId } = route.params;
  const { showToast } = useToast();

  const [product, setProduct] = useState<ProductDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openingChat, setOpeningChat] = useState(false);
  const [addingToCart, setAddingToCart] = useState(false);
  const [reviews, setReviews] = useState<Review[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchProduct(productId);
      setProduct(data);
      const reviewsPage = await fetchProductReviews(productId);
      setReviews(reviewsPage.results);
    } catch (caught) {
      setError(getErrorMessage(caught));
    } finally {
      setLoading(false);
    }
  }, [productId]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      // Touch state only after an await so nothing runs synchronously from the
      // effect body (react-hooks/set-state-in-effect).
      await Promise.resolve();
      if (cancelled) return;
      await load();
    })();
    return () => {
      cancelled = true;
    };
  }, [load]);

  const handleChat = useCallback(async () => {
    setOpeningChat(true);
    try {
      const conversation = await openConversationForProduct(productId);
      navigation.navigate('Conversation', { conversationId: conversation.id });
    } catch (caught) {
      showToast(getErrorMessage(caught));
    } finally {
      setOpeningChat(false);
    }
  }, [productId, navigation, showToast]);

  const handleAddToCart = useCallback(async () => {
    if (!product) {
      return;
    }
    setAddingToCart(true);
    try {
      await addToCart({ product_id: product.id, quantity: 1 });
      showToast('Added to cart', { type: 'success' });
    } catch (caught) {
      showToast(getErrorMessage(caught));
    } finally {
      setAddingToCart(false);
    }
  }, [product, showToast]);

  if (loading) {
    return <LoadingSpinner label="Loading listing…" />;
  }

  if (error || !product) {
    return <ErrorState message={error ?? 'This listing is no longer available.'} onRetry={load} />;
  }

  const imageUrls =
    product.images.length > 0
      ? product.images.map((image) => image.image)
      : product.primary_image
        ? [product.primary_image]
        : [];

  return (
    <View style={styles.container}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <ImageCarousel imageUrls={imageUrls} />

        <View style={styles.body}>
          <View style={styles.metaRow}>
            <View style={styles.conditionBadge}>
              <Text style={styles.conditionText}>{CONDITION_LABELS[product.condition]}</Text>
            </View>
            <Text style={styles.postedAt}>{formatRelativeTime(product.created_at)}</Text>
          </View>

          <Text style={styles.price}>{formatPrice(product.price)}</Text>
          <Text style={styles.name}>{product.name}</Text>

          <View style={styles.locationRow}>
            <Ionicons name="location-outline" size={16} color={colors.textSecondary} />
            <Text style={styles.location}>{product.location || 'Location not specified'}</Text>
          </View>

          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Description</Text>
            <Text style={styles.description}>
              {product.description || 'No description provided.'}
            </Text>
          </View>

          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Seller</Text>
            <View style={styles.sellerCard}>
              <SellerAvatar name={product.seller.full_name} uri={product.seller.profile_picture} />
              <View style={styles.sellerInfo}>
                <Text style={styles.sellerName}>{product.seller.full_name}</Text>
                <RatingStars
                  rating={product.seller.average_rating}
                  count={product.seller.rating_count}
                />
              </View>
            </View>
          </View>

          <View style={styles.section}>
            <Text style={styles.sectionTitle}>
              Reviews{product.rating_count > 0 ? ` (${product.rating_count})` : ''}
            </Text>
            {reviews.length > 0 ? (
              <View style={styles.reviewsList}>
                {reviews.map((review) => (
                  <ReviewItem key={review.id} review={review} />
                ))}
              </View>
            ) : (
              <Text style={styles.description}>No reviews yet for this listing.</Text>
            )}
          </View>
        </View>
      </ScrollView>

      <SafeAreaView edges={['bottom']} style={styles.actionBar}>
        <View style={styles.favoriteWrap}>
          <FavoriteButton productId={product.id} size={26} />
        </View>
        <Button
          title="Add to Cart"
          loading={addingToCart}
          onPress={() => void handleAddToCart()}
          style={styles.actionButton}
        />
        <Button
          title="Chat"
          variant="secondary"
          loading={openingChat}
          onPress={() => void handleChat()}
          style={styles.actionButton}
        />
      </SafeAreaView>
    </View>
  );
}

function SellerAvatar({ name, uri }: { name: string; uri: string | null }) {
  const avatarUrl = resolveImageUrl(uri);
  return avatarUrl ? (
    <Image source={{ uri: avatarUrl }} style={styles.avatar} />
  ) : (
    <View style={[styles.avatar, styles.avatarFallback]}>
      <Text style={styles.avatarText}>{initials(name)}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scroll: {
    paddingBottom: 120,
  },
  body: {
    padding: spacing.lg,
    gap: spacing.sm,
  },
  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  conditionBadge: {
    backgroundColor: colors.primary,
    borderRadius: radii.round,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  conditionText: {
    color: colors.onPrimary,
    fontSize: 12,
    fontWeight: '600',
  },
  postedAt: {
    ...typography.label,
    fontSize: 12,
  },
  price: {
    ...typography.title,
    fontSize: 26,
    color: colors.primary,
  },
  name: {
    ...typography.title,
    fontSize: 20,
  },
  locationRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  location: {
    ...typography.label,
  },
  section: {
    marginTop: spacing.lg,
    gap: spacing.sm,
  },
  sectionTitle: {
    ...typography.title,
    fontSize: 16,
  },
  description: {
    ...typography.body,
    lineHeight: 22,
  },
  sellerCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.lg,
    padding: spacing.md,
  },
  avatar: {
    width: 48,
    height: 48,
    borderRadius: 24,
  },
  avatarFallback: {
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: {
    color: colors.onPrimary,
    fontSize: 16,
    fontWeight: '700',
  },
  sellerInfo: {
    gap: 4,
  },
  sellerName: {
    ...typography.body,
    fontWeight: '600',
  },
  reviewsList: {
    gap: spacing.md,
  },
  actionBar: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  favoriteWrap: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    overflow: 'hidden',
  },
  actionButton: {
    flex: 1,
  },
});
