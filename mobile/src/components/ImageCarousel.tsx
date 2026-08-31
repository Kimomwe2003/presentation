import { useState } from 'react';
import { FlatList, Image, StyleSheet, View, useWindowDimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { colors, spacing } from '../theme';
import { resolveImageUrl } from '../utils/format';

interface ImageCarouselProps {
  imageUrls: string[];
}

/** Paged image carousel with dot indicators for the product detail screen. */
export default function ImageCarousel({ imageUrls }: ImageCarouselProps) {
  const { width } = useWindowDimensions();
  const [index, setIndex] = useState(0);

  const resolved = imageUrls
    .map((url) => resolveImageUrl(url))
    .filter((url): url is string => url !== null);

  const urls = resolved.length > 0 ? resolved : null;

  return (
    <View>
      <FlatList
        horizontal
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        data={urls ?? [null]}
        keyExtractor={(_, i) => String(i)}
        onMomentumScrollEnd={(event) => {
          const next = Math.round(event.nativeEvent.contentOffset.x / width);
          setIndex(next);
        }}
        renderItem={({ item }) =>
          item ? (
            <Image source={{ uri: item }} style={[styles.image, { width }]} />
          ) : (
            <View style={[styles.image, styles.placeholder, { width }]}>
              <Ionicons name="image-outline" size={56} color={colors.disabled} />
            </View>
          )
        }
      />
      {urls && urls.length > 1 ? (
        <View style={styles.dots}>
          {urls.map((_, i) => (
            <View key={i} style={[styles.dot, i === index && styles.dotActive]} />
          ))}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  image: {
    aspectRatio: 1,
    backgroundColor: colors.background,
  },
  placeholder: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  dots: {
    position: 'absolute',
    bottom: spacing.md,
    alignSelf: 'center',
    flexDirection: 'row',
    gap: spacing.xs,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: 'rgba(255,255,255,0.5)',
  },
  dotActive: {
    backgroundColor: colors.onPrimary,
  },
});
