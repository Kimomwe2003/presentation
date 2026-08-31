import { StyleSheet, Text, View } from 'react-native';

import { colors, spacing, typography } from '../theme';

interface PlaceholderScreenProps {
  title: string;
  description: string;
}

/** Reused by tab stubs until their prompts land. */
export default function PlaceholderScreen({ title, description }: PlaceholderScreenProps) {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>{title}</Text>
      <Text style={styles.description}>{description}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    padding: spacing.xl,
  },
  title: {
    ...typography.title,
  },
  description: {
    ...typography.subtitle,
    textAlign: 'center',
  },
});
