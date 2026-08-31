import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { forgotPasswordRequest } from '../../api/auth';
import { getErrorMessage } from '../../api/errors';
import {
  AuthField,
  AuthScreen,
  PrimaryAction,
  SlideUpFade,
  authStyles,
} from '../../components/AuthUI';
import ErrorBanner from '../../components/ErrorBanner';
import { useToast } from '../../context/ToastContext';
import type { AuthStackParamList } from '../../navigation/types';
import { colors, spacing } from '../../theme';

type Props = NativeStackScreenProps<AuthStackParamList, 'ForgotPassword'>;

export default function ForgotPasswordScreen({ navigation }: Props) {
  const { showToast } = useToast();
  const [email, setEmail] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const canSubmit = email.trim().length > 0 && !submitting;

  const handleSubmit = async () => {
    if (!canSubmit) {
      return;
    }
    setSubmitting(true);
    setFormError(null);
    try {
      const normalizedEmail = email.trim().toLowerCase();
      const response = await forgotPasswordRequest(normalizedEmail);
      showToast('Reset code generated', { type: 'success' });
      navigation.navigate('ResetPassword', {
        email: normalizedEmail,
        devCode: response.debug_code,
      });
    } catch (error) {
      setFormError(getErrorMessage(error));
      showToast('Could not send reset code', { type: 'error' });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthScreen
      title="Forgot password"
      subtitle="Enter your account email and we'll issue a reset code"
      footer={
        <Text style={authStyles.footerLink} onPress={() => navigation.navigate('Login')}>
          Back to log in
        </Text>
      }
    >
      {formError ? <ErrorBanner message={formError} /> : null}
      <View style={authStyles.form}>
        <SlideUpFade delay={150}>
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
        <SlideUpFade delay={220}>
          <PrimaryAction title="Send reset code" loading={submitting} onPress={handleSubmit} />
        </SlideUpFade>
        <SlideUpFade delay={280}>
          <View style={styles.noteCard}>
            <Text style={styles.noteTitle}>How it works</Text>
            <Text style={styles.noteBody}>
              A 6-digit reset code valid for 15 minutes will be issued for your account. Enter it
              on the next screen together with your new password.
            </Text>
          </View>
        </SlideUpFade>
      </View>
    </AuthScreen>
  );
}

const styles = StyleSheet.create({
  noteCard: {
    backgroundColor: '#F8FAFC',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    padding: spacing.sm,
    gap: spacing.xs,
  },
  noteTitle: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  noteBody: {
    fontSize: 13,
    lineHeight: 18,
    color: colors.textSecondary,
  },
});
