import { Ionicons } from '@expo/vector-icons';
import { StyleSheet, Text, View } from 'react-native';

import { colors, spacing, typography } from '../theme';
import Button from './Button';

interface ErrorStateProps {
  message?: string;
  onRetry: () => void;
}

export default function ErrorState({
  message = 'Something went wrong.',
  onRetry,
}: ErrorStateProps) {
  return (
    <View style={styles.container}>
      <Ionicons name="cloud-offline-outline" size={44} color={colors.disabled} />
      <Text style={styles.message}>{message}</Text>
      <Button title="Try again" variant="secondary" onPress={onRetry} style={styles.action} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    gap: spacing.sm,
    paddingVertical: spacing.xxl,
    paddingHorizontal: spacing.xl,
  },
  message: {
    ...typography.body,
    textAlign: 'center',
  },
  action: {
    marginTop: spacing.md,
    alignSelf: 'center',
  },
});
