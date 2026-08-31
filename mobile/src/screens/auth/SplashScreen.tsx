import { Image, StyleSheet, Text, View } from 'react-native';

import LoadingSpinner from '../../components/LoadingSpinner';
import { colors, typography } from '../../theme';

/** Shown while the stored session (if any) is validated against /users/me/. */
export default function SplashScreen() {
  return (
    <View style={styles.container}>
      <View style={styles.brand}>
        <Image
          source={require('../../../assets/icon.png')}
          style={styles.logo}
          accessibilityIgnoresInvertColors
        />
        <Text style={typography.title}>ReuseHub</Text>
      </View>
      <LoadingSpinner />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 40,
  },
  brand: {
    alignItems: 'center',
    gap: 12,
  },
  logo: {
    width: 96,
    height: 96,
    borderRadius: 24,
  },
});
