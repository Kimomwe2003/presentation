import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { getErrorMessage } from '../../api/errors';
import { resetPasswordRequest } from '../../api/auth';
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

type Props = NativeStackScreenProps<AuthStackParamList, 'ResetPassword'>;

export default function ResetPasswordScreen({ navigation, route }: Props) {
  const { email, devCode } = route.params;
  const { showToast } = useToast();
  const [code, setCode] = useState(devCode ?? '');
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const canSubmit =
    code.trim().length === 6 &&
    password.length > 0 &&
    confirmation.length > 0 &&
    !submitting;

  const handleSubmit = async () => {
    if (!canSubmit) {
      return;
    }
    setSubmitting(true);
    setFormError(null);
    try {
      await resetPasswordRequest({
        email: email.trim().toLowerCase(),
        code: code.trim(),
        new_password: password,
        new_password_confirmation: confirmation,
      });
      showToast('Password reset — log in with your new password', { type: 'success' });
      navigation.popToTop();
      navigation.navigate('Login');
    } catch (error) {
      setFormError(getErrorMessage(error));
      showToast('Could not reset password', { type: 'error' });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthScreen
      title="Set a new password"
      subtitle={`Enter the reset code for ${email}`}
      footer={
        <>
          {devCode ? (
            <Text style={styles.devCodeNote}>Your reset code: {devCode}</Text>
          ) : null}
          <Text
            style={authStyles.footerLink}
            onPress={() => navigation.navigate('ForgotPassword')}
          >
            Request a new code
          </Text>
          <View style={authStyles.footerRow}>
            <Text style={authStyles.footerText}>Remembered it? </Text>
            <Text style={authStyles.footerLinkStrong} onPress={() => navigation.navigate('Login')}>
              Log in
            </Text>
          </View>
        </>
      }
    >
      {formError ? <ErrorBanner message={formError} /> : null}
      <View style={authStyles.form}>
        <SlideUpFade delay={150}>
          <AuthField
            label="Reset code"
            value={code}
            onChangeText={setCode}
            placeholder="6-digit code"
            keyboardType="number-pad"
            maxLength={6}
            autoCapitalize="none"
            autoComplete="one-time-code"
            editable={!submitting}
          />
        </SlideUpFade>
        <SlideUpFade delay={200}>
          <AuthField
            label="New password"
            value={password}
            onChangeText={setPassword}
            placeholder="New password"
            secureTextEntry
            autoCapitalize="none"
            autoComplete="new-password"
            onSubmitEditing={handleSubmit}
            editable={!submitting}
          />
        </SlideUpFade>
        <SlideUpFade delay={280}>
          <AuthField
            label="Confirm new password"
            value={confirmation}
            onChangeText={setConfirmation}
            placeholder="Repeat new password"
            secureTextEntry
            autoCapitalize="none"
            autoComplete="new-password"
            onSubmitEditing={handleSubmit}
            editable={!submitting}
          />
        </SlideUpFade>
        <SlideUpFade delay={360}>
          <PrimaryAction title="Reset password" loading={submitting} onPress={handleSubmit} />
        </SlideUpFade>
      </View>
    </AuthScreen>
  );
}

const styles = StyleSheet.create({
  devCodeNote: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.primary,
    textAlign: 'center',
    marginBottom: spacing.xs,
  },
});
