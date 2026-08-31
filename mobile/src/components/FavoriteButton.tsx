import { Ionicons } from '@expo/vector-icons';
import { Pressable, StyleSheet, type StyleProp, type ViewStyle } from 'react-native';

import { useFavorites } from '../context/FavoritesContext';
import { colors } from '../theme';

interface FavoriteButtonProps {
  productId: number;
  size?: number;
  style?: StyleProp<ViewStyle>;
}

/** Circular heart toggle, wired to FavoritesContext (backend round-trip). */
export default function FavoriteButton({ productId, size = 22, style }: FavoriteButtonProps) {
  const { isFavorite, toggleFavorite } = useFavorites();
  const active = isFavorite(productId);

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={active ? 'Remove from favorites' : 'Add to favorites'}
      hitSlop={8}
      style={({ pressed }) => [styles.container, pressed && styles.pressed, style]}
      onPress={() => void toggleFavorite(productId)}
    >
      <Ionicons
        name={active ? 'heart' : 'heart-outline'}
        size={size}
        color={active ? colors.error : colors.textSecondary}
      />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.surface,
    borderRadius: 999,
    width: 36,
    height: 36,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOpacity: 0.12,
    shadowRadius: 4,
    shadowOffset: { width: 0, height: 2 },
    elevation: 3,
  },
  pressed: {
    opacity: 0.7,
  },
});
