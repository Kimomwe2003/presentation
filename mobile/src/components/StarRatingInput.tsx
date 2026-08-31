import { Ionicons } from '@expo/vector-icons';
import { Pressable, StyleSheet, View } from 'react-native';

import { colors, spacing } from '../theme';

interface StarRatingInputProps {
  value: number;
  onChange: (value: number) => void;
  size?: number;
}

/** Tappable 1–5 star input for review creation (Prompt 15). */
export default function StarRatingInput({ value, onChange, size = 36 }: StarRatingInputProps) {
  return (
    <View style={styles.row} accessibilityRole="adjustable" accessibilityLabel="Rating">
      {[1, 2, 3, 4, 5].map((star) => (
        <Pressable
          key={star}
          onPress={() => onChange(star)}
          hitSlop={spacing.sm}
          accessibilityRole="button"
          accessibilityLabel={`${star} star${star === 1 ? '' : 's'}`}
          testID={`star-${star}`}
        >
          <Ionicons
            name={star <= value ? 'star' : 'star-outline'}
            size={size}
            color={star <= value ? colors.primary : colors.disabled}
          />
        </Pressable>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
});
