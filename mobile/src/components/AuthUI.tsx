import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import {
  ActivityIndicator,
  Animated,
  Easing,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  type StyleProp,
  type TextInputProps,
  type ViewStyle,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';

import { slate } from '../theme';

const SPRING = Easing.bezier(0.22, 1, 0.36, 1);
const GRID = Array.from({ length: 22 }, (_, i) => i * 40);
const ROWS = Array.from({ length: 30 }, (_, i) => i * 40);

function BlueprintGrid() {
  return (
    <View style={StyleSheet.absoluteFill} pointerEvents="none">
      {GRID.map((x) => (
        <View key={x} style={[styles.gridVertical, { left: x }]} />
      ))}
      {ROWS.map((y) => (
        <View key={y} style={[styles.gridHorizontal, { top: y }]} />
      ))}
    </View>
  );
}

function PulseDot({
  size,
  color,
  delay,
  duration,
  style,
}: {
  size: number;
  color: string;
  delay: number;
  duration: number;
  style?: StyleProp<ViewStyle>;
}) {
  const value = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(value, { toValue: 1, duration, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
        Animated.timing(value, { toValue: 0, duration, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
      ]),
    );
    const timer = setTimeout(() => loop.start(), delay * 1000);
    return () => {
      clearTimeout(timer);
      loop.stop();
    };
  }, [delay, duration, value]);

  return (
    <Animated.View
      style={[
        {
          width: size,
          height: size,
          borderRadius: size / 2,
          backgroundColor: color,
          opacity: value.interpolate({ inputRange: [0, 1], outputRange: [0.8, 1] }),
          transform: [{ scale: value.interpolate({ inputRange: [0, 1], outputRange: [1, 1.2] }) }],
        },
        style,
      ]}
    />
  );
}

export function ScaleIn({ delay, style, children }: { delay: number; style?: StyleProp<ViewStyle>; children: ReactNode }) {
  const value = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.timing(value, { toValue: 1, duration: 800, delay, easing: SPRING, useNativeDriver: true }).start();
  }, [value, delay]);

  return (
    <Animated.View
      style={[
        { opacity: value, transform: [{ scale: value.interpolate({ inputRange: [0, 1], outputRange: [0.95, 1] }) }] },
        style,
      ]}
    >
      {children}
    </Animated.View>
  );
}

export function SlideUpFade({
  delay,
  style,
  children,
}: {
  delay: number;
  style?: StyleProp<ViewStyle>;
  children: ReactNode;
}) {
  const value = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.timing(value, {
      toValue: 1,
      duration: 600,
      delay,
      easing: SPRING,
      useNativeDriver: true,
    }).start();
  }, [value, delay]);

  return (
    <Animated.View
      style={[
        { opacity: value, transform: [{ translateY: value.interpolate({ inputRange: [0, 1], outputRange: [20, 0] }) }] },
        style,
      ]}
    >
      {children}
    </Animated.View>
  );
}

export function AuthIdentity() {
  return (
    <View style={styles.identity}>
      <View style={styles.ring}>
        <PulseDot size={6} color={slate.line} delay={0.1} duration={2000} style={styles.dotOne} />
        <PulseDot size={6} color={slate.lineSoft} delay={0.4} duration={2000} style={styles.dotTwo} />
        <PulseDot size={8} color={slate.line} delay={0.7} duration={2500} style={styles.dotThree} />
        <View style={styles.lineOne} />
        <View style={styles.lineTwo} />
        <View style={styles.lineThree} />
      </View>
      <View style={styles.logo}>
        <Ionicons name="cube-outline" size={26} color={slate.line} />
      </View>
    </View>
  );
}

interface AuthFieldProps extends TextInputProps {
  label: string;
}

export function AuthField({ label, style, ...rest }: AuthFieldProps) {
  const id = useId();
  const focus = useRef(new Animated.Value(0)).current;
  const [focused, setFocused] = useState(false);

  useEffect(() => {
    Animated.timing(focus, {
      toValue: focused ? 1 : 0,
      duration: 200,
      easing: Easing.out(Easing.ease),
      useNativeDriver: false,
    }).start();
  }, [focused, focus]);

  return (
    <View style={styles.fieldGroup}>
      <Text nativeID={`${id}-label`} style={styles.fieldLabel}>
        {label}
      </Text>
      <Animated.View
        style={[
          styles.fieldBox,
          {
            borderColor: focus.interpolate({ inputRange: [0, 1], outputRange: [slate.border, slate.primary] }),
            shadowOpacity: focus.interpolate({ inputRange: [0, 1], outputRange: [0, 0.05] }),
          },
        ]}
      >
        <TextInput
          accessibilityLabelledBy={`${id}-label`}
          placeholderTextColor={slate.placeholder}
          style={[styles.fieldInput, style]}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          {...rest}
        />
      </Animated.View>
    </View>
  );
}

export function PrimaryAction({ title, loading, onPress }: { title: string; loading: boolean; onPress: () => void }) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ busy: loading, disabled: loading }}
      accessibilityLabel={title}
      disabled={loading}
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        pressed && !loading && styles.buttonPressed,
        loading && styles.buttonDisabled,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={slate.white} />
      ) : (
        <View style={styles.buttonContent}>
          <Text style={styles.buttonText}>{title}</Text>
          <Ionicons name="arrow-forward" size={20} color={slate.white} />
        </View>
      )}
    </Pressable>
  );
}

export interface AuthScreenProps {
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
}

export function AuthScreen({ title, subtitle, children, footer }: AuthScreenProps) {
  const float = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(float, { toValue: 1, duration: 3000, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
        Animated.timing(float, { toValue: 0, duration: 3000, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [float]);

  return (
    <SafeAreaView style={styles.safeArea}>
      <BlueprintGrid />
      <View style={styles.accent} pointerEvents="none">
        <Animated.View
          style={{
            transform: [
              { translateY: float.interpolate({ inputRange: [0, 1], outputRange: [0, -10] }) },
              { rotate: float.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '2deg'] }) },
            ],
          }}
        >
          <View style={styles.accentSquare} />
          <View style={styles.accentCircle} />
          <View style={styles.accentLine} />
        </Animated.View>
      </View>
      <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          <ScaleIn delay={0}>
            <AuthIdentity />
          </ScaleIn>
          <SlideUpFade delay={100}>
            <View style={styles.header}>
              <Text style={styles.title}>{title}</Text>
              {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
            </View>
          </SlideUpFade>
          {children}
          {footer ? (
            <SlideUpFade delay={440}>
              <View style={styles.footer}>{footer}</View>
            </SlideUpFade>
          ) : null}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: slate.white,
  },
  flex: {
    flex: 1,
  },
  content: {
    flexGrow: 1,
    paddingTop: 56,
    paddingHorizontal: 32,
    paddingBottom: 34,
  },
  gridVertical: {
    position: 'absolute',
    top: 0,
    bottom: 0,
    width: 1,
    backgroundColor: slate.grid,
  },
  gridHorizontal: {
    position: 'absolute',
    left: 0,
    right: 0,
    height: 1,
    backgroundColor: slate.grid,
  },
  accent: {
    position: 'absolute',
    top: 40,
    right: -30,
    width: 300,
    height: 600,
    opacity: 0.4,
  },
  accentSquare: {
    position: 'absolute',
    top: 80,
    right: 60,
    width: 40,
    height: 40,
    borderWidth: 1,
    borderColor: slate.lineSoft,
    transform: [{ rotate: '45deg' }],
  },
  accentCircle: {
    position: 'absolute',
    bottom: 80,
    right: 10,
    width: 110,
    height: 110,
    borderRadius: 55,
    borderWidth: 2,
    borderColor: slate.grid,
  },
  accentLine: {
    position: 'absolute',
    top: 0,
    bottom: 0,
    left: 0,
    width: 1,
    backgroundColor: slate.grid,
  },
  identity: {
    width: 64,
    height: 64,
    marginBottom: 32,
  },
  ring: {
    position: 'absolute',
    left: -16,
    top: -16,
    width: 96,
    height: 96,
    borderRadius: 48,
    borderWidth: 1,
    borderStyle: 'dashed',
    borderColor: slate.border,
  },
  dotOne: {
    position: 'absolute',
    left: 4,
    top: 4,
  },
  dotTwo: {
    position: 'absolute',
    left: 64,
    top: 4,
  },
  dotThree: {
    position: 'absolute',
    left: 34,
    top: 69,
  },
  lineOne: {
    position: 'absolute',
    left: 12.2,
    top: 32,
    width: 39.6,
    height: 1,
    borderTopWidth: 1,
    borderStyle: 'dashed',
    borderColor: slate.border,
    transform: [{ rotate: '225deg' }],
  },
  lineTwo: {
    position: 'absolute',
    left: 12.2,
    top: 32,
    width: 39.6,
    height: 1,
    borderTopWidth: 1,
    borderStyle: 'dashed',
    borderColor: slate.border,
    transform: [{ rotate: '315deg' }],
  },
  lineThree: {
    position: 'absolute',
    left: 32.2,
    top: 32,
    width: 1,
    height: 37,
    borderLeftWidth: 1,
    borderStyle: 'dashed',
    borderColor: slate.border,
  },
  logo: {
    width: 64,
    height: 64,
    borderRadius: 16,
    borderWidth: 2,
    borderStyle: 'dashed',
    borderColor: slate.lineSoft,
    backgroundColor: slate.accent,
    alignItems: 'center',
    justifyContent: 'center',
  },
  header: {
    gap: 10,
    marginBottom: 48,
  },
  title: {
    fontSize: 32,
    fontWeight: '600',
    lineHeight: 35,
    color: slate.primary,
  },
  subtitle: {
    fontSize: 18,
    lineHeight: 26,
    color: slate.secondary,
  },
  form: {
    gap: 20,
  },
  fieldGroup: {
    gap: 6,
  },
  fieldLabel: {
    fontSize: 14,
    fontWeight: '500',
    color: slate.primary,
    marginLeft: 4,
  },
  fieldBox: {
    borderWidth: 1,
    borderColor: slate.border,
    borderRadius: 16,
    backgroundColor: slate.white,
    shadowColor: slate.primary,
    shadowOffset: { width: 0, height: 0 },
    shadowRadius: 4,
    shadowOpacity: 0,
  },
  fieldInput: {
    height: 56,
    paddingHorizontal: 16,
    fontSize: 16,
    color: slate.primary,
  },
  button: {
    height: 56,
    borderRadius: 16,
    backgroundColor: slate.primary,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: slate.primary,
    shadowOffset: { width: 0, height: 10 },
    shadowRadius: 15,
    shadowOpacity: 0.1,
    elevation: 4,
  },
  buttonContent: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  buttonText: {
    color: slate.white,
    fontSize: 16,
    fontWeight: '600',
  },
  buttonPressed: {
    transform: [{ scale: 0.98 }],
  },
  buttonDisabled: {
    opacity: 0.55,
  },
  footer: {
    alignItems: 'center',
    marginTop: 48,
    gap: 8,
  },
  footerRow: {
    flexDirection: 'row',
  },
  footerLink: {
    fontSize: 14,
    color: slate.secondary,
  },
  footerText: {
    fontSize: 14,
    color: slate.secondary,
  },
  footerLinkStrong: {
    fontSize: 14,
    fontWeight: '600',
    color: slate.primary,
  },
});
export const authStyles = styles;
