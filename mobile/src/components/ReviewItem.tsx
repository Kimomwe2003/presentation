import { StyleSheet, Text, View } from 'react-native';

import type { Review } from '../api/types';
import RatingStars from './RatingStars';
import { colors, radii, spacing, typography } from '../theme';
import { formatRelativeTime, initials } from '../utils/format';

interface ReviewItemProps {
  review: Review;
}

/** A single review row (Prompt 15), reused on product details + seller profile. */
export default function ReviewItem({ review }: ReviewItemProps) {
  return (
    <View style={styles.card}>
      <View style={styles.header}>
        <View style={styles.avatar}>
          <Text style={styles.avatarText}>{initials(review.buyer.full_name)}</Text>
        </View>
        <View style={styles.headerText}>
          <Text style={styles.author}>{review.buyer.full_name}</Text>
          <Text style={styles.time}>{formatRelativeTime(review.created_at)}</Text>
        </View>
        <RatingStars rating={review.rating} count={null} />
      </View>
      {review.comment ? <Text style={styles.comment}>{review.comment}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.md,
    padding: spacing.md,
    gap: spacing.sm,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  avatar: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: {
    color: colors.onPrimary,
    fontSize: 14,
    fontWeight: '700',
  },
  headerText: {
    flex: 1,
    gap: 2,
  },
  author: {
    ...typography.body,
    fontWeight: '600',
  },
  time: {
    ...typography.label,
  },
  comment: {
    ...typography.body,
    lineHeight: 20,
  },
});
