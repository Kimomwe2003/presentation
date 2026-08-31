import { useState } from 'react';
import { Image, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { Ionicons } from '@expo/vector-icons';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { getErrorMessage } from '../../api/errors';
import {
  updateProfile,
  updateProfilePicture,
  removeProfilePicture,
} from '../../api/auth';
import Button from '../../components/Button';
import Card from '../../components/Card';
import ErrorBanner from '../../components/ErrorBanner';
import TextInput from '../../components/TextInput';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import type { RootStackParamList } from '../../navigation/types';
import { colors, radii, spacing, typography } from '../../theme';

type Props = NativeStackScreenProps<RootStackParamList, 'EditProfile'>;

export default function EditProfileScreen({ navigation }: Props) {
  const { user, refetchUser } = useAuth();
  const { showToast } = useToast();

  const [fullName, setFullName] = useState(user?.profile.full_name ?? '');
  const [phoneNumber, setPhoneNumber] = useState(user?.profile.phone_number ?? '');
  const [address, setAddress] = useState(user?.profile.address ?? '');
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const hasChanges =
    fullName.trim() !== (user?.profile.full_name ?? '') ||
    phoneNumber.trim() !== (user?.profile.phone_number ?? '') ||
    address.trim() !== (user?.profile.address ?? '');

  const handleSave = async () => {
    if (!hasChanges) {
      navigation.goBack();
      return;
    }
    setSubmitting(true);
    setFormError(null);
    try {
      await updateProfile({
        full_name: fullName.trim(),
        phone_number: phoneNumber.trim() || null,
        address: address.trim() || null,
      });
      await refetchUser();
      showToast('Profile updated', { type: 'success' });
      navigation.goBack();
    } catch (error) {
      setFormError(getErrorMessage(error));
    } finally {
      setSubmitting(false);
    }
  };

  const handlePickImage = async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      allowsEditing: true,
      aspect: [1, 1],
      quality: 0.8,
    });
    if (result.canceled || !result.assets?.[0]) {
      return;
    }
    setSubmitting(true);
    setFormError(null);
    try {
      await updateProfilePicture(result.assets[0].uri);
      await refetchUser();
      showToast('Profile picture updated', { type: 'success' });
    } catch (error) {
      setFormError(getErrorMessage(error));
    } finally {
      setSubmitting(false);
    }
  };

  const handleRemovePicture = async () => {
    setSubmitting(true);
    setFormError(null);
    try {
      await removeProfilePicture();
      await refetchUser();
      showToast('Profile picture removed', { type: 'success' });
    } catch (error) {
      setFormError(getErrorMessage(error));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      keyboardShouldPersistTaps="handled"
    >
      {formError ? <ErrorBanner message={formError} /> : null}

      <Card style={styles.pictureCard}>
        <View style={styles.pictureRow}>
          {user?.profile.profile_picture ? (
            <Image source={{ uri: user.profile.profile_picture }} style={styles.avatar} />
          ) : (
            <View style={[styles.avatar, styles.avatarPlaceholder]}>
              <Ionicons name="person" size={40} color={colors.textSecondary} />
            </View>
          )}
          <View style={{ flex: 1, gap: spacing.sm }}>
            <Pressable
              style={({ pressed }) => [styles.pictureBtn, pressed && styles.pressed]}
              onPress={handlePickImage}
              disabled={submitting}
            >
              <Text style={styles.pictureBtnText}>
                {user?.profile.profile_picture ? 'Change photo' : 'Add photo'}
              </Text>
            </Pressable>
            {user?.profile.profile_picture ? (
              <Pressable
                style={({ pressed }) => [styles.pictureBtn, pressed && styles.pressed]}
                onPress={handleRemovePicture}
                disabled={submitting}
              >
                <Text style={[styles.pictureBtnText, { color: colors.error }]}>Remove</Text>
              </Pressable>
            ) : null}
          </View>
        </View>
      </Card>

      <Card style={styles.formCard}>
        <TextInput
          label="Full name"
          value={fullName}
          onChangeText={setFullName}
          placeholder="Jane Doe"
          autoCapitalize="words"
          editable={!submitting}
        />
        <TextInput
          label="Phone number"
          value={phoneNumber}
          onChangeText={setPhoneNumber}
          placeholder="+255 700 000 000"
          keyboardType="phone-pad"
          autoComplete="tel"
          editable={!submitting}
        />
        <TextInput
          label="Address"
          value={address}
          onChangeText={setAddress}
          placeholder="City, Country"
          autoCapitalize="words"
          editable={!submitting}
        />
      </Card>

      <Button
        title="Save changes"
        loading={submitting}
        disabled={!hasChanges}
        onPress={() => void handleSave()}
      />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.lg,
    gap: spacing.lg,
  },
  pictureCard: {
    gap: spacing.md,
  },
  pictureRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.lg,
  },
  avatar: {
    width: 80,
    height: 80,
    borderRadius: 40,
  },
  avatarPlaceholder: {
    backgroundColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  pictureBtn: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  pictureBtnText: {
    ...typography.body,
    fontWeight: '600',
    color: colors.primary,
  },
  pressed: {
    opacity: 0.7,
  },
  formCard: {
    gap: spacing.md,
  },
});
