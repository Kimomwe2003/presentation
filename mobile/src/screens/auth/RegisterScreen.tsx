import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { getErrorMessage } from '../../api/errors';
import { AuthField, AuthScreen, PrimaryAction, SlideUpFade, authStyles } from '../../components/AuthUI';
import ErrorBanner from '../../components/ErrorBanner';
import { useAuth } from '../../context/AuthContext';
import type { AuthStackParamList } from '../../navigation/types';
import { colors, radii, spacing, typography } from '../../theme';

type Props = NativeStackScreenProps<AuthStackParamList, 'Register'>;

export default function RegisterScreen({ navigation }: Props) {
  const { signUp } = useAuth();
  const [role, setRole] = useState<'BUYER' | 'SELLER'>('BUYER');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirmation, setPasswordConfirmation] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const canSubmit =
    fullName.trim().length > 0 &&
    email.trim().length > 0 &&
    password.length > 0 &&
    passwordConfirmation.length > 0 &&
    !submitting;

  const handleSubmit = async () => {
    if (!canSubmit) {
      return;
    }
    setSubmitting(true);
    setFormError(null);
    try {
      await signUp({
        email: email.trim().toLowerCase(),
        full_name: fullName.trim(),
        phone_number: phoneNumber.trim() || undefined,
        role,
        password,
        password_confirmation: passwordConfirmation,
      });
    } catch (error) {
      setFormError(getErrorMessage(error));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthScreen
      title="Create your account"
      subtitle="Join ReuseHub to discover great items or sell your pre-loved goods."
      footer={
        <View style={authStyles.footerRow}>
          <Text style={authStyles.footerText}>Already have an account? </Text>
          <Text style={authStyles.footerLinkStrong} onPress={() => navigation.navigate('Login')}>
            Log in
          </Text>
        </View>
      }
    >
      {formError ? <ErrorBanner message={formError} /> : null}
      <View style={authStyles.form}>
        <SlideUpFade delay={120}>
          <View style={styles.roleContainer}>
            <Text style={styles.roleLabel}>I want to join as a:</Text>
            <View style={styles.roleRow}>
              <Pressable
                style={[styles.roleCard, role === 'BUYER' && styles.roleCardActive]}
                onPress={() => setRole('BUYER')}
                disabled={submitting}
              >
                <Ionicons
                  name={role === 'BUYER' ? 'bag' : 'bag-outline'}
                  size={24}
                  color={role === 'BUYER' ? colors.primary : colors.textSecondary}
                />
                <Text style={[styles.roleTitle, role === 'BUYER' && styles.roleTitleActive]}>
                  Buyer
                </Text>
                <Text style={styles.roleSubtext}>Shop & discover items</Text>
              </Pressable>

              <Pressable
                style={[styles.roleCard, role === 'SELLER' && styles.roleCardActive]}
                onPress={() => setRole('SELLER')}
                disabled={submitting}
              >
                <Ionicons
                  name={role === 'SELLER' ? 'pricetag' : 'pricetag-outline'}
                  size={24}
                  color={role === 'SELLER' ? colors.primary : colors.textSecondary}
                />
                <Text style={[styles.roleTitle, role === 'SELLER' && styles.roleTitleActive]}>
                  Seller
                </Text>
                <Text style={styles.roleSubtext}>List & sell products</Text>
              </Pressable>
            </View>
          </View>
        </SlideUpFade>

        <SlideUpFade delay={200}>
          <AuthField
            label="Full name"
            value={fullName}
            onChangeText={setFullName}
            placeholder="Jane Doe"
            autoCapitalize="words"
            editable={!submitting}
          />
        </SlideUpFade>
        <SlideUpFade delay={260}>
          <AuthField
            label="Email"
            value={email}
            onChangeText={setEmail}
            placeholder="you@example.com"
            keyboardType="email-address"
            autoCapitalize="none"
            autoComplete="email"
            autoCorrect={false}
            editable={!submitting}
          />
        </SlideUpFade>
        <SlideUpFade delay={320}>
          <AuthField
            label="Phone number (optional)"
            value={phoneNumber}
            onChangeText={setPhoneNumber}
            placeholder="+255 700 000 000"
            keyboardType="phone-pad"
            autoComplete="tel"
            editable={!submitting}
          />
        </SlideUpFade>
        <SlideUpFade delay={380}>
          <AuthField
            label="Password"
            value={password}
            onChangeText={setPassword}
            placeholder="At least 8 characters"
            secureTextEntry
            autoCapitalize="none"
            autoComplete="new-password"
            editable={!submitting}
          />
        </SlideUpFade>
        <SlideUpFade delay={440}>
          <AuthField
            label="Confirm password"
            value={passwordConfirmation}
            onChangeText={setPasswordConfirmation}
            placeholder="Repeat your password"
            secureTextEntry
            autoCapitalize="none"
            autoComplete="new-password"
            onSubmitEditing={handleSubmit}
            editable={!submitting}
          />
        </SlideUpFade>
        <SlideUpFade delay={500}>
          <PrimaryAction
            title={`Create ${role === 'SELLER' ? 'Seller' : 'Buyer'} Account`}
            loading={submitting}
            onPress={handleSubmit}
          />
        </SlideUpFade>
      </View>
    </AuthScreen>
  );
}

const styles = StyleSheet.create({
  roleContainer: {
    gap: spacing.xs,
    marginBottom: spacing.xs,
  },
  roleLabel: {
    ...typography.label,
    fontSize: 13,
    fontWeight: '600',
    color: colors.text,
  },
  roleRow: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  roleCard: {
    flex: 1,
    padding: spacing.md,
    borderRadius: radii.md,
    borderWidth: 1.5,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
  },
  roleCardActive: {
    borderColor: colors.primary,
    backgroundColor: '#EFF6FF',
  },
  roleTitle: {
    ...typography.body,
    fontWeight: '700',
    color: colors.text,
  },
  roleTitleActive: {
    color: colors.primary,
  },
  roleSubtext: {
    ...typography.label,
    fontSize: 11,
    color: colors.textSecondary,
    textAlign: 'center',
  },
});