import { forwardRef, useId } from 'react';
import {
  StyleSheet,
  Text,
  TextInput as RNTextInput,
  View,
  type TextInputProps,
} from 'react-native';

import { colors, radii, spacing } from '../theme';

interface AppTextInputProps extends TextInputProps {
  label?: string;
  error?: string;
  hint?: string;
}

const AppTextInput = forwardRef<RNTextInput, AppTextInputProps>(function AppTextInput(
  { label, error, hint, style, ...rest },
  ref,
) {
  const id = useId();
  return (
    <View style={styles.container}>
      {label ? (
        <Text nativeID={`${id}-label`} style={styles.label}>
          {label}
        </Text>
      ) : null}
      <RNTextInput
        ref={ref}
        accessibilityLabelledBy={label ? `${id}-label` : undefined}
        placeholderTextColor={colors.textSecondary}
        style={[styles.input, error ? styles.inputError : null, style]}
        {...rest}
      />
      {error ? (
        <Text style={styles.error}>{error}</Text>
      ) : hint ? (
        <Text style={styles.hint}>{hint}</Text>
      ) : null}
    </View>
  );
});

export default AppTextInput;

const styles = StyleSheet.create({
  container: {
    gap: spacing.xs,
  },
  label: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.text,
  },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    fontSize: 15,
    color: colors.text,
    backgroundColor: colors.surface,
  },
  inputError: {
    borderColor: colors.error,
  },
  error: {
    fontSize: 12,
    color: colors.error,
  },
  hint: {
    fontSize: 12,
    color: colors.textSecondary,
  },
});
