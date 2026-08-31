import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import type { ProductCondition, ProductFilters } from '../../api/types';
import AppTextInput from '../../components/TextInput';
import Button from '../../components/Button';
import LoadingSpinner from '../../components/LoadingSpinner';
import { useCategories } from '../../hooks/useCategories';
import type { RootStackParamList } from '../../navigation/types';
import { colors, radii, spacing, typography } from '../../theme';
import { CONDITION_LABELS } from '../../utils/format';

type Props = NativeStackScreenProps<RootStackParamList, 'Filters'>;

const CONDITIONS: ProductCondition[] = ['NEW', 'LIKE_NEW', 'GOOD', 'FAIR', 'USED'];

export default function FiltersScreen({ navigation, route }: Props) {
  const current = route.params?.current ?? {};
  const { categories, loading, error, reload } = useCategories();

  const [category, setCategory] = useState<number | undefined>(current.category);
  const [condition, setCondition] = useState<ProductCondition | undefined>(current.condition);
  const [minPrice, setMinPrice] = useState(
    current.minPrice != null ? String(current.minPrice) : '',
  );
  const [maxPrice, setMaxPrice] = useState(
    current.maxPrice != null ? String(current.maxPrice) : '',
  );
  const [location, setLocation] = useState(current.location ?? '');

  const apply = () => {
    const filters: ProductFilters = {
      category,
      condition,
      minPrice: minPrice ? Number(minPrice) : undefined,
      maxPrice: maxPrice ? Number(maxPrice) : undefined,
      location: location.trim() || undefined,
    };
    navigation.navigate('Tabs', { screen: 'Search', params: { filters } });
  };

  const clearAll = () => {
    setCategory(undefined);
    setCondition(undefined);
    setMinPrice('');
    setMaxPrice('');
    setLocation('');
  };

  return (
    <View style={styles.container}>
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <Text style={styles.sectionTitle}>Category</Text>
        {loading ? (
          <LoadingSpinner size="small" />
        ) : error ? (
          <Pressable onPress={reload} hitSlop={8}>
            <Text style={styles.retry}>{'Couldn\u0027t load categories — tap to retry'}</Text>
          </Pressable>
        ) : (
          <View style={styles.wrap}>
            <Option label="Any" active={category == null} onPress={() => setCategory(undefined)} />
            {categories.map((item) => (
              <Option
                key={item.id}
                label={item.name}
                active={category === item.id}
                onPress={() => setCategory(item.id)}
              />
            ))}
          </View>
        )}

        <Text style={styles.sectionTitle}>Condition</Text>
        <View style={styles.wrap}>
          <Option label="Any" active={condition == null} onPress={() => setCondition(undefined)} />
          {CONDITIONS.map((item) => (
            <Option
              key={item}
              label={CONDITION_LABELS[item]}
              active={condition === item}
              onPress={() => setCondition(item)}
            />
          ))}
        </View>

        <Text style={styles.sectionTitle}>Price range</Text>
        <View style={styles.priceRow}>
          <AppTextInput
            label="Minimum"
            value={minPrice}
            onChangeText={setMinPrice}
            keyboardType="numeric"
            placeholder="0"
            style={styles.priceInput}
          />
          <AppTextInput
            label="Maximum"
            value={maxPrice}
            onChangeText={setMaxPrice}
            keyboardType="numeric"
            placeholder="No limit"
            style={styles.priceInput}
          />
        </View>

        <Text style={styles.sectionTitle}>Location</Text>
        <AppTextInput
          label="Location"
          value={location}
          onChangeText={setLocation}
          placeholder="e.g. Dar es Salaam"
        />
      </ScrollView>

      <View style={styles.footer}>
        <Button
          title="Clear all"
          variant="secondary"
          onPress={clearAll}
          style={styles.footerButton}
        />
        <Button title="Apply filters" onPress={apply} style={styles.footerButton} />
      </View>
    </View>
  );
}

function Option({
  label,
  active,
  onPress,
}: {
  label: string;
  active: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected: active }}
      style={({ pressed }) => [
        styles.option,
        active && styles.optionActive,
        pressed && styles.pressed,
      ]}
      onPress={onPress}
    >
      <Text style={[styles.optionText, active && styles.optionTextActive]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.lg,
    gap: spacing.sm,
    paddingBottom: spacing.xl,
  },
  sectionTitle: {
    ...typography.title,
    fontSize: 16,
    marginTop: spacing.md,
  },
  wrap: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  option: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.round,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    backgroundColor: colors.surface,
  },
  optionActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  optionText: {
    fontSize: 13,
    fontWeight: '500',
    color: colors.text,
  },
  optionTextActive: {
    color: colors.onPrimary,
    fontWeight: '600',
  },
  pressed: {
    opacity: 0.8,
  },
  retry: {
    ...typography.label,
    color: colors.primary,
    fontWeight: '600',
  },
  priceRow: {
    flexDirection: 'row',
    gap: spacing.md,
  },
  priceInput: {
    flex: 1,
  },
  footer: {
    flexDirection: 'row',
    gap: spacing.md,
    padding: spacing.lg,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.surface,
  },
  footerButton: {
    flex: 1,
  },
});
