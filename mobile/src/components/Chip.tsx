import { Pressable, StyleSheet, Text } from 'react-native';
import { colors, radii, spacing } from '../theme';

interface ChipProps {
  label: string;
  selected?: boolean;
  onPress?: () => void;
}

/** A selectable pill used for single-choice filters (condition, status, ...). */
export default function Chip({ label, selected = false, onPress }: ChipProps) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected }}
      onPress={onPress}
      style={({ pressed }) => [styles.chip, selected && styles.selected, pressed && styles.pressed]}
    >
      <Text style={[styles.label, selected && styles.selectedLabel]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  chip: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radii.round,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  selected: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  pressed: {
    opacity: 0.8,
  },
  label: {
    fontSize: 13,
    color: colors.text,
    fontWeight: '500',
  },
  selectedLabel: {
    color: colors.onPrimary,
  },
});
