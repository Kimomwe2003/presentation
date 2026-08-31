import { StyleSheet, Text, View } from 'react-native';
import { colors, radii, spacing } from '../theme';

type BadgeVariant = 'primary' | 'success' | 'danger' | 'neutral' | 'warning';

interface BadgeProps {
  label: string;
  variant?: BadgeVariant;
}

const VARIANTS: Record<BadgeVariant, { bg: string; fg: string }> = {
  primary: { bg: colors.primary, fg: colors.onPrimary },
  success: { bg: colors.success, fg: colors.onPrimary },
  danger: { bg: colors.error, fg: colors.onPrimary },
  neutral: { bg: colors.border, fg: colors.text },
  warning: { bg: colors.errorSurface, fg: colors.error },
};

export default function Badge({ label, variant = 'neutral' }: BadgeProps) {
  const palette = VARIANTS[variant];
  return (
    <View style={[styles.badge, { backgroundColor: palette.bg }]}>
      <Text style={[styles.label, { color: palette.fg }]} numberOfLines={1}>
        {label}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    borderRadius: radii.round,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    alignSelf: 'flex-start',
  },
  label: {
    fontSize: 12,
    fontWeight: '600',
  },
});
