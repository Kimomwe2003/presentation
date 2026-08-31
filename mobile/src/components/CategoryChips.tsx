import { Pressable, ScrollView, StyleSheet, Text } from 'react-native';

import type { Category } from '../api/types';
import { colors, radii, spacing } from '../theme';

interface CategoryChipsProps {
  categories: Category[];
  onSelect: (category: Category) => void;
}

/** Horizontal scrollable category shortcuts (Home header). */
export default function CategoryChips({ categories, onSelect }: CategoryChipsProps) {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.content}
    >
      {categories.map((category) => (
        <Pressable
          key={category.id}
          accessibilityRole="button"
          style={({ pressed }) => [styles.chip, pressed && styles.pressed]}
          onPress={() => onSelect(category)}
        >
          <Text style={styles.label}>{category.name}</Text>
        </Pressable>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: {
    gap: spacing.sm,
    paddingRight: spacing.lg,
  },
  chip: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.round,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
  },
  pressed: {
    backgroundColor: colors.border,
  },
  label: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.text,
  },
});
