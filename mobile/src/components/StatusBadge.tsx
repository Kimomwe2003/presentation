import { StyleSheet, Text, View } from 'react-native';

import { colors, radii, spacing, typography } from '../theme';

/** Badge palette per backend order / item status code. */
const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  pending_payment: { bg: '#FFF4E0', text: '#8A5A00' },
  pending: { bg: '#FFF4E0', text: '#8A5A00' },
  paid: { bg: '#E3F0FB', text: '#155A8A' },
  confirmed: { bg: '#E3F0FB', text: '#155A8A' },
  shipped: { bg: '#E6EEF5', text: '#3D5A75' },
  delivered: { bg: '#E0F2F1', text: '#00695C' },
  completed: { bg: '#E6F4EA', text: colors.success },
  cancelled: { bg: '#FDEBEA', text: colors.error },
  payment_failed: { bg: '#FDEBEA', text: colors.error },
  refunded: { bg: '#F3E8F5', text: '#6A1B9A' },
};

const DEFAULT = { bg: '#ECEFF1', text: '#5C636A' };

interface StatusBadgeProps {
  status: string;
  label: string;
}

export default function StatusBadge({ status, label }: StatusBadgeProps) {
  const palette = STATUS_COLORS[status] ?? DEFAULT;
  return (
    <View style={[styles.badge, { backgroundColor: palette.bg }]}>
      <Text style={[styles.label, { color: palette.text }]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    alignSelf: 'flex-start',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: radii.round,
  },
  label: {
    ...typography.label,
    fontWeight: '600',
    fontSize: 12,
  },
});
