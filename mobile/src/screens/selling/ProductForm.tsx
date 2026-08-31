import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import { useCallback, useState } from 'react';
import { Image, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { deleteProductImage, type ProductWritePayload } from '../../api/catalog';
import { getErrorMessage } from '../../api/errors';
import type { ProductCondition, ProductDetail, ProductImage } from '../../api/types';
import Button from '../../components/Button';
import TextInput from '../../components/TextInput';
import { useToast } from '../../context/ToastContext';
import { useCategories } from '../../hooks/useCategories';
import { colors, radii, spacing, typography } from '../../theme';
import { CONDITION_LABELS, resolveImageUrl } from '../../utils/format';

const CONDITIONS = Object.keys(CONDITION_LABELS) as ProductCondition[];

interface ProductFormProps {
  /** Present in edit mode; absent when creating a new listing. */
  initial?: ProductDetail;
  submitLabel: string;
  submitting: boolean;
  onSubmit: (payload: ProductWritePayload, newImageUris: string[]) => Promise<void>;
}

/**
 * Shared create/edit form for listings: product fields, a multi-image picker
 * and inline validation. New images are kept locally until submit; existing
 * images (edit mode) are removable immediately via the catalog API.
 */
export default function ProductForm({
  initial,
  submitLabel,
  submitting,
  onSubmit,
}: ProductFormProps) {
  const { showToast } = useToast();
  const { categories } = useCategories();

  const [name, setName] = useState(initial?.name ?? '');
  const [description, setDescription] = useState(initial?.description ?? '');
  const [price, setPrice] = useState(initial ? String(initial.price) : '');
  const [condition, setCondition] = useState<ProductCondition | null>(initial?.condition ?? null);
  const [quantity, setQuantity] = useState(initial ? String(initial.quantity) : '');
  const [location, setLocation] = useState(initial?.location ?? '');
  const [categoryId, setCategoryId] = useState<number | null>(initial?.category?.id ?? null);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const [remoteImages, setRemoteImages] = useState<ProductImage[]>(initial?.images ?? []);
  const [localImages, setLocalImages] = useState<string[]>([]);
  const [removingImage, setRemovingImage] = useState<number | null>(null);

  const pickImages = useCallback(async () => {
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      showToast('Photo library access is required to add listing photos.');
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      allowsMultipleSelection: true,
      selectionLimit: 8,
      // Kept modest so photos stay under the backend's 5 MB per-file cap.
      quality: 0.6,
    });
    if (!result.canceled) {
      const uris = result.assets.map((asset) => asset.uri);
      setLocalImages((prev) => [...prev, ...uris].slice(0, 8));
    }
  }, [showToast]);

  const removeRemote = useCallback(
    async (image: ProductImage) => {
      if (!initial || removingImage != null) {
        return;
      }
      setRemovingImage(image.id);
      try {
        await deleteProductImage(initial.id, image.id);
        setRemoteImages((prev) => prev.filter((item) => item.id !== image.id));
      } catch (e) {
        showToast(getErrorMessage(e));
      } finally {
        setRemovingImage(null);
      }
    },
    [initial, removingImage, showToast],
  );

  const removeLocal = useCallback((uri: string) => {
    setLocalImages((prev) => prev.filter((item) => item !== uri));
  }, []);

  const handleSubmit = useCallback(() => {
    const nextErrors: Record<string, string> = {};
    const parsedPrice = Number(price);
    const parsedQuantity = quantity === '' ? null : Number(quantity);

    if (!name.trim()) {
      nextErrors.name = 'Name is required.';
    }
    if (!price || !Number.isFinite(parsedPrice) || parsedPrice <= 0) {
      nextErrors.price = 'Enter a price greater than zero.';
    }
    if (!condition) {
      nextErrors.condition = 'Select a condition.';
    }
    if (parsedQuantity != null && (!Number.isInteger(parsedQuantity) || parsedQuantity < 0)) {
      nextErrors.quantity = 'Quantity must be a whole number.';
    }
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) {
      return;
    }

    void onSubmit(
      {
        name: name.trim(),
        description: description.trim() || undefined,
        price: parsedPrice.toFixed(2),
        condition: condition as ProductCondition,
        quantity: parsedQuantity ?? undefined,
        location: location.trim() || undefined,
        category: categoryId,
      },
      localImages,
    );
  }, [name, description, price, condition, quantity, location, categoryId, localImages, onSubmit]);

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={styles.content}
      keyboardShouldPersistTaps="handled"
    >
      <View style={styles.field}>
        <TextInput
          label="Name"
          placeholder="e.g. Used laptop"
          value={name}
          onChangeText={setName}
          error={errors.name}
          autoCapitalize="sentences"
        />
      </View>

      <View style={styles.field}>
        <TextInput
          label="Price (TZS)"
          placeholder="0.00"
          value={price}
          onChangeText={setPrice}
          keyboardType="decimal-pad"
          error={errors.price}
        />
      </View>

      <View style={styles.field}>
        <Text style={styles.label}>Condition</Text>
        <View style={styles.chipRow}>
          {CONDITIONS.map((code) => (
            <Chip
              key={code}
              label={CONDITION_LABELS[code]}
              selected={condition === code}
              onPress={() => setCondition(code)}
            />
          ))}
        </View>
        {errors.condition ? <Text style={styles.fieldError}>{errors.condition}</Text> : null}
      </View>

      <View style={styles.field}>
        <TextInput
          label="Quantity available (optional)"
          placeholder="1"
          value={quantity}
          onChangeText={setQuantity}
          keyboardType="number-pad"
          error={errors.quantity}
        />
      </View>

      <View style={styles.field}>
        <TextInput
          label="Location (optional)"
          placeholder="e.g. Dar es Salaam"
          value={location}
          onChangeText={setLocation}
          autoCapitalize="words"
        />
      </View>

      <View style={styles.field}>
        <Text style={styles.label}>Category (optional)</Text>
        {categories.length > 0 ? (
          <View style={styles.chipRow}>
            {categories.map((category) => (
              <Chip
                key={category.id}
                label={category.name}
                selected={categoryId === category.id}
                onPress={() => setCategoryId((prev) => (prev === category.id ? null : category.id))}
              />
            ))}
          </View>
        ) : null}
      </View>

      <View style={styles.field}>
        <TextInput
          label="Description (optional)"
          placeholder="Describe the item's condition, specs, etc."
          value={description}
          onChangeText={setDescription}
          multiline
          numberOfLines={4}
          style={styles.multiline}
          textAlignVertical="top"
        />
      </View>

      <View style={styles.field}>
        <Text style={styles.label}>Photos</Text>
        <View style={styles.photoRow}>
          {remoteImages.map((image) => (
            <PhotoThumb
              key={image.id}
              uri={image.image}
              onRemove={() => void removeRemote(image)}
            />
          ))}
          {localImages.map((uri) => (
            <PhotoThumb key={uri} uri={uri} onRemove={() => removeLocal(uri)} />
          ))}
          {remoteImages.length + localImages.length < 8 ? (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Add photos"
              onPress={() => void pickImages()}
              style={({ pressed }) => [styles.addPhoto, pressed && styles.pressed]}
            >
              <Ionicons name="add" size={28} color={colors.primary} />
            </Pressable>
          ) : null}
        </View>
        <Text style={styles.hint}>
          First photo becomes the listing cover. Tap a photo to remove it.
        </Text>
      </View>

      <Button
        title={submitLabel}
        loading={submitting}
        onPress={handleSubmit}
        style={styles.submit}
      />
    </ScrollView>
  );
}

function Chip({
  label,
  selected,
  onPress,
}: {
  label: string;
  selected: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected }}
      onPress={onPress}
      style={({ pressed }) => [
        styles.chip,
        selected && styles.chipSelected,
        pressed && styles.pressed,
      ]}
    >
      <Text style={[styles.chipLabel, selected && styles.chipLabelSelected]}>{label}</Text>
    </Pressable>
  );
}

function PhotoThumb({ uri, onRemove }: { uri: string; onRemove: () => void }) {
  const thumbUrl = resolveImageUrl(uri) ?? uri;
  return (
    <View style={styles.thumb}>
      <Image source={{ uri: thumbUrl }} style={styles.thumbImage} />
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Remove photo"
        onPress={onRemove}
        style={({ pressed }) => [styles.removeBadge, pressed && styles.pressed]}
      >
        <Ionicons name="close" size={14} color={colors.onPrimary} />
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.lg,
    gap: spacing.md,
    paddingBottom: spacing.xxl,
  },
  field: {
    gap: spacing.xs,
  },
  label: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.text,
  },
  fieldError: {
    fontSize: 12,
    color: colors.error,
  },
  hint: {
    fontSize: 12,
    color: colors.textSecondary,
  },
  multiline: {
    minHeight: 100,
  },
  chipRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  chip: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.round,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    backgroundColor: colors.surface,
  },
  chipSelected: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  chipLabel: {
    ...typography.label,
    fontSize: 13,
    color: colors.text,
    fontWeight: '600',
  },
  chipLabelSelected: {
    color: colors.onPrimary,
  },
  photoRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.md,
  },
  thumb: {
    width: 88,
    height: 88,
    borderRadius: radii.md,
    overflow: 'hidden',
  },
  thumbImage: {
    width: '100%',
    height: '100%',
    backgroundColor: colors.background,
  },
  removeBadge: {
    position: 'absolute',
    top: 4,
    right: 4,
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: colors.overlay,
    alignItems: 'center',
    justifyContent: 'center',
  },
  addPhoto: {
    width: 88,
    height: 88,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderStyle: 'dashed',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.surface,
  },
  pressed: {
    opacity: 0.7,
  },
  submit: {
    marginTop: spacing.sm,
  },
});
