import { Ionicons } from '@expo/vector-icons';
import { StyleSheet, Text, View } from 'react-native';

import { colors, spacing, typography } from '../theme';

interface RatingStarsProps {
  rating?: number | null;
  count?: number | null;
}

export default function RatingStars({ rating, count }: RatingStarsProps) {
  if (rating == null) {
    return (
      <View style={styles.row}>
        <View style={styles.stars}>
          {[0, 1, 2, 3, 4].map((star) => (
            <Ionicons key={star} name="star-outline" size={14} color={colors.disabled} />
          ))}
        </View>
        <Text style={styles.label}>New seller</Text>
      </View>
    );
  }

  const filled = Math.round(rating);
  return (
    <View style={styles.row}>
      <View style={styles.stars}>
        {[0, 1, 2, 3, 4].map((star) => (
          <Ionicons
            key={star}
            name={star < filled ? 'star' : 'star-outline'}
            size={14}
            color={colors.primary}
          />
        ))}
      </View>
      <Text style={styles.label}>
        {rating.toFixed(1)} {count != null ? `(${count})` : ''}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  stars: {
    flexDirection: 'row',
    gap: 1,
  },
  label: {
    ...typography.label,
  },
});
