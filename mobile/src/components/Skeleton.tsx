import { useEffect, useState } from 'react';
import {
  Animated,
  StyleSheet,
  type DimensionValue,
  type StyleProp,
  type ViewStyle,
} from 'react-native';

import { colors } from '../theme';

interface SkeletonProps {
  width?: DimensionValue;
  height?: number;
  borderRadius?: number;
  style?: StyleProp<ViewStyle>;
}

/** Pulsing placeholder block used to build loading skeletons. */
export default function Skeleton({
  width = '100%',
  height = 14,
  borderRadius = 4,
  style,
}: SkeletonProps) {
  // useState initializer keeps the Animated.Value stable without touching a
  // ref during render (react-hooks/refs).
  const [opacity] = useState(() => new Animated.Value(0.4));

  useEffect(() => {
    const animation = Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, { toValue: 1, duration: 650, useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 0.4, duration: 650, useNativeDriver: true }),
      ]),
    );
    animation.start();
    return () => animation.stop();
  }, [opacity]);

  return <Animated.View style={[styles.block, { width, height, borderRadius, opacity }, style]} />;
}

const styles = StyleSheet.create({
  block: {
    backgroundColor: colors.border,
  },
});
