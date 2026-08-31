/**
 * Global toast surface. The single place non-form feedback (success notes,
 * transient errors) is shown — screens never call `Alert.alert` directly.
 */
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { Animated, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { colors, radii, spacing } from '../theme';

type ToastType = 'error' | 'success' | 'info';

interface ToastOptions {
  type?: ToastType;
  durationMs?: number;
}

interface ToastContextValue {
  showToast: (message: string, options?: ToastOptions) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const BG_COLORS: Record<ToastType, string> = {
  error: colors.error,
  success: colors.success,
  info: colors.textSecondary,
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const insets = useSafeAreaInsets();
  // Created via useState initializer so the Animated.Value is stable but its
  // `current` is never touched during render (react-hooks/refs).
  const [opacity] = useState(() => new Animated.Value(0));
  const [message, setMessage] = useState<string | null>(null);
  const [type, setType] = useState<ToastType>('info');
  const hideTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showToast = useCallback(
    (text: string, options?: ToastOptions) => {
      setMessage(text);
      setType(options?.type ?? 'error');
      opacity.setValue(0);
      Animated.timing(opacity, { toValue: 1, duration: 180, useNativeDriver: true }).start();

      if (hideTimer.current) {
        clearTimeout(hideTimer.current);
      }
      hideTimer.current = setTimeout(() => {
        Animated.timing(opacity, { toValue: 0, duration: 220, useNativeDriver: true }).start(() =>
          setMessage(null),
        );
      }, options?.durationMs ?? 3200);
    },
    [opacity],
  );

  const value = useMemo(() => ({ showToast }), [showToast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      {message != null && (
        <Animated.View
          pointerEvents="none"
          style={[
            styles.toast,
            { top: insets.top + 12, opacity, backgroundColor: BG_COLORS[type] },
          ]}
        >
          <View style={styles.inner}>
            <Text style={styles.text}>{message}</Text>
          </View>
        </Animated.View>
      )}
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
}

const styles = StyleSheet.create({
  toast: {
    position: 'absolute',
    left: spacing.lg,
    right: spacing.lg,
    borderRadius: radii.md,
    shadowColor: '#000',
    shadowOpacity: 0.15,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 },
    elevation: 6,
  },
  inner: {
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
  },
  text: {
    color: colors.onPrimary,
    fontSize: 14,
    fontWeight: '500',
  },
});
