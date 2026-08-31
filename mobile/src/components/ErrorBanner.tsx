import { StyleSheet, Text, View } from 'react-native';

import { colors, radii, spacing } from '../theme';

interface ErrorBannerProps {
  message: string;
}

/** Inline, form-level error surface. Transient/global errors use useToast instead. */
export default function ErrorBanner({ message }: ErrorBannerProps) {
  return (
    <View accessibilityRole="alert" style={styles.banner}>
      <Text style={styles.text}>{message}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  banner: {
    backgroundColor: colors.errorSurface,
    borderColor: colors.error,
    borderWidth: 1,
    borderRadius: radii.sm,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
  },
  text: {
    color: colors.error,
    fontSize: 14,
    fontWeight: '500',
  },
});
