import { StyleSheet, View } from 'react-native';

import { spacing } from '../theme';
import Skeleton from './Skeleton';

/** 2-column grid of product-card placeholders shown during the initial load. */
export default function ProductGridSkeleton() {
  const cards = [0, 1, 2, 3];
  return (
    <View style={styles.grid}>
      {cards.map((key) => (
        <View key={key} style={styles.cell}>
          <Skeleton width="100%" height={160} borderRadius={12} />
          <View style={styles.body}>
            <Skeleton width="90%" height={14} />
            <Skeleton width="50%" height={16} />
            <Skeleton width="70%" height={12} />
          </View>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    padding: spacing.lg,
  },
  cell: {
    width: '48%',
    marginBottom: spacing.lg,
  },
  body: {
    marginTop: spacing.md,
    gap: spacing.sm,
  },
});
