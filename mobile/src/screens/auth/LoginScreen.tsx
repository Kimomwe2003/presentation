import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { getErrorMessage } from '../../api/errors';
import { AuthField, AuthScreen, PrimaryAction, SlideUpFade, authStyles } from '../../components/AuthUI';
import ErrorBanner from '../../components/ErrorBanner';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import type { AuthStackParamList } from '../../navigation/types';
import { colors, radii, spacing } from '../../theme';

type Props = NativeStackScreenProps<AuthStackParamList, 'Login'>;

export default function LoginScreen({ navigation }: Props) {
  const { signIn } = useAuth();
  const { showToast } = useToast();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const canSubmit = email.trim().length > 0 && password.length > 0 && !submitting;

  const handleSubmit = async () => {
    if (!canSubmit) {
      return;
    }
    setSubmitting(true);
    setFormError(null);
    try {
      await signIn({ email: email.trim().toLowerCase(), password });
    } catch (error) {
      setFormError(getErrorMessage(error));
      showToast('Login failed', { type: 'error' });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthScreen
      title="Welcome back"
      subtitle="Log in to keep buying and selling on ReuseHub"
      footer={
        <>
          <Text style={authStyles.footerLink} onPress={() => navigation.navigate('ForgotPassword')}>
            Forgot password?
          </Text>
          <View style={authStyles.footerRow}>
            <Text style={authStyles.footerText}>Don&apos;t have an account? </Text>
            <Text style={authStyles.footerLinkStrong} onPress={() => navigation.navigate('Register')}>
              Sign up
            </Text>
          </View>
        </>
      }
    >
      {formError ? <ErrorBanner message={formError} /> : null}
      <View style={authStyles.form}>
        <SlideUpFade delay={150}>
          <View style={styles.quickFillContainer}>
            <Text style={styles.quickFillTitle}>Quick fill demo role:</Text>
            <View style={styles.quickFillRow}>
              <Pressable
                style={({ pressed }) => [
                  styles.quickChip,
                  email === 'admin@gmail.com' && styles.quickChipActive,
                  pressed && { opacity: 0.7 },
                ]}
                onPress={() => {
                  setEmail('admin@gmail.com');
                  setPassword('Admin12345!');
                }}
              >
                <Text
                  style={[
                    styles.quickChipText,
                    email === 'admin@gmail.com' && styles.quickChipTextActive,
                  ]}
                >
                  Admin
                </Text>
              </Pressable>
              <Pressable
                style={({ pressed }) => [
                  styles.quickChip,
                  email === 'sadakimomwe@gmail.com' && styles.quickChipActive,
                  pressed && { opacity: 0.7 },
                ]}
                onPress={() => {
                  setEmail('sadakimomwe@gmail.com');
                  setPassword('Password123!');
                }}
              >
                <Text
                  style={[
                    styles.quickChipText,
                    email === 'sadakimomwe@gmail.com' && styles.quickChipTextActive,
                  ]}
                >
                  Buyer
                </Text>
              </Pressable>
              <Pressable
                style={({ pressed }) => [
                  styles.quickChip,
                  email === 'lidyakimomwe@gmail.com' && styles.quickChipActive,
                  pressed && { opacity: 0.7 },
                ]}
                onPress={() => {
                  setEmail('lidyakimomwe@gmail.com');
                  setPassword('Password123!');
                }}
              >
                <Text
                  style={[
                    styles.quickChipText,
                    email === 'lidyakimomwe@gmail.com' && styles.quickChipTextActive,
                  ]}
                >
                  Seller
                </Text>
              </Pressable>
            </View>
          </View>
        </SlideUpFade>

        <SlideUpFade delay={200}>
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
        <SlideUpFade delay={280}>
          <AuthField
            label="Password"
            value={password}
            onChangeText={setPassword}
            placeholder="Your password"
            secureTextEntry
            autoCapitalize="none"
            autoComplete="password"
            onSubmitEditing={handleSubmit}
            editable={!submitting}
          />
        </SlideUpFade>
        <SlideUpFade delay={360}>
          <PrimaryAction title="Log in" loading={submitting} onPress={handleSubmit} />
        </SlideUpFade>
      </View>
    </AuthScreen>
  );
}

const styles = StyleSheet.create({
  quickFillContainer: {
    backgroundColor: '#F8FAFC',
    borderRadius: radii.md,
    padding: spacing.sm,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    marginBottom: spacing.xs,
    gap: spacing.xs,
  },
  quickFillTitle: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  quickFillRow: {
    flexDirection: 'row',
    gap: spacing.xs,
  },
  quickChip: {
    flex: 1,
    paddingVertical: 6,
    paddingHorizontal: 8,
    borderRadius: radii.sm,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#CBD5E1',
    alignItems: 'center',
    justifyContent: 'center',
  },
  quickChipActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  quickChipText: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.text,
  },
  quickChipTextActive: {
    color: '#FFFFFF',
  },
});