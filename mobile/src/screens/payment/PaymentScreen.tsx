/**
 * PaymentScreen — ClickPesa USSD-Push mobile money checkout.
 *
 * Phone number formats accepted:
 *   • 0XXXXXXXXX  (local Tanzanian — auto-converted to 255XXXXXXXXX)
 *   • 255XXXXXXXXX (international format — sent as-is)
 *
 * Flow (CLICKPESA_PAYMENT_ARCHITECTURE.md):
 *  1. Buyer enters mobile money number → "Pay Now"
 *  2. Backend calls ClickPesa → USSD prompt pushed to phone
 *  3. App polls /api/payments/<orderId>/status/ with back-off
 *  4. ClickPesa webhook → backend marks order PAID
 *  5. Poll detects PAID → 2.5-second success modal → back to order
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Animated,
  Easing,
  KeyboardAvoidingView,
  Modal,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput as RNTextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { fetchPaymentStatus, initiatePayment, verifyPayment } from '../../api/payments';
import type { PaymentState } from '../../api/types';
import Button from '../../components/Button';
import type { RootStackParamList } from '../../navigation/types';
import { colors, radii, spacing, typography } from '../../theme';

type Props = NativeStackScreenProps<RootStackParamList, 'Payment'>;
type ScreenState = 'loading' | 'idle' | 'starting' | 'pending' | 'success' | 'failed';

/** Exponential back-off poll intervals in ms */
const POLL_INTERVALS_MS = [3000, 5000, 8000, 10000, 15000];

/** Map ClickPesa channel names to display labels */
const CHANNEL_LABELS: Record<string, { label: string; color: string }> = {
  'M-PESA': { label: 'M-Pesa', color: '#E40000' },
  'TIGO-PESA': { label: 'Tigo Pesa', color: '#0093D0' },
  'AIRTEL-MONEY': { label: 'Airtel Money', color: '#E40000' },
  'HALOPESA': { label: 'Halopesa', color: '#FF6600' },
  'HALO PESA': { label: 'Halopesa', color: '#FF6600' },
};

/**
 * Normalise phone to 255XXXXXXXXX.
 * Accepts: 0712345678 → 255712345678 or 255712345678 (unchanged)
 */
function normalisePhone(raw: string): string {
  const digits = raw.replace(/\D/g, '');
  if (digits.startsWith('0') && digits.length === 10) {
    return '255' + digits.slice(1);
  }
  return digits;
}

/** Validate the normalised 12-digit TZ number */
function isValidPhone(digits: string): boolean {
  return /^255\d{9}$/.test(digits);
}

/** Format a ClickPesa channel string (e.g. "TIGO-PESA") into a display label */
function formatChannel(channel: string): { label: string; color: string } | null {
  if (!channel) return null;
  const normalised = channel.trim().toUpperCase().replace(/[\s_-]/g, '');
  if (normalised.includes('MPESA')) return { label: 'M-Pesa', color: '#E40000' };
  if (normalised.includes('TIGO')) return { label: 'Tigo Pesa', color: '#0093D0' };
  if (normalised.includes('AIRTEL')) return { label: 'Airtel Money', color: '#E40000' };
  if (normalised.includes('HALO')) return { label: 'Halopesa', color: '#FF6600' };
  return { label: channel.trim(), color: '#666' };
}

export default function PaymentScreen({ navigation, route }: Props) {
  const { orderId } = route.params;

  const [screen, setScreen] = useState<ScreenState>('loading');
  const [rawPhone, setRawPhone] = useState('');
  const [phoneError, setPhoneError] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [state, setState] = useState<PaymentState | null>(null);
  const [showSuccess, setShowSuccess] = useState(false);

  // Animation refs
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const fadeAnim = useRef(new Animated.Value(0)).current;
  const slideAnim = useRef(new Animated.Value(30)).current;

  // Fade in the idle form on mount
  useEffect(() => {
    if (screen === 'idle') {
      Animated.parallel([
        Animated.timing(fadeAnim, {
          toValue: 1,
          duration: 350,
          useNativeDriver: true,
        }),
        Animated.timing(slideAnim, {
          toValue: 0,
          duration: 350,
          easing: Easing.out(Easing.quad),
          useNativeDriver: true,
        }),
      ]).start();
    }
  }, [screen, fadeAnim, slideAnim]);

  // Pulsing ring for pending state
  useEffect(() => {
    if (screen !== 'pending') return;
    const anim = Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, {
          toValue: 1.15,
          duration: 900,
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: true,
        }),
        Animated.timing(pulseAnim, {
          toValue: 1,
          duration: 900,
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: true,
        }),
      ]),
    );
    anim.start();
    return () => anim.stop();
  }, [screen, pulseAnim]);

  const orderTotal = state?.payment?.amount ?? null;
  const orderStatusLabel = state?.order.status_label ?? '';
  const normalisedPhone = normalisePhone(rawPhone);

  const applyState = useCallback(
    (next: PaymentState) => {
      setState(next);
      setErrorMessage(null);
      if (next.payment?.status === 'successful' || next.order.status === 'paid') {
        setScreen('success');
        setShowSuccess(true);
        setTimeout(() => {
          setShowSuccess(false);
          navigation.goBack();
        }, 2500);
      } else if (next.payment?.status === 'failed' || next.payment?.status === 'expired') {
        setScreen('failed');
      } else if (next.payment?.status === 'pending') {
        setScreen('pending');
      } else {
        setScreen('idle');
      }
    },
    [navigation],
  );

  // Load existing payment state on mount
  useEffect(() => {
    let active = true;
    fetchPaymentStatus(orderId)
      .then((next) => { if (active) applyState(next); })
      .catch(() => { if (active) setScreen('idle'); });
    return () => { active = false; };
  }, [orderId, applyState]);

  // Poll with back-off during PENDING state
  useEffect(() => {
    if (screen !== 'pending') return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let attempt = 0;

    const poll = async () => {
      try {
        const next = await fetchPaymentStatus(orderId);
        if (cancelled) return;
        setState(next);
        if (next.payment?.status === 'successful' || next.order.status === 'paid') {
          applyState(next); return;
        }
        if (next.payment?.status === 'failed' || next.payment?.status === 'expired') {
          applyState(next); return;
        }
      } catch { /* keep polling on network error */ }
      if (cancelled) return;
      const delay = POLL_INTERVALS_MS[Math.min(attempt, POLL_INTERVALS_MS.length - 1)];
      attempt += 1;
      timer = setTimeout(poll, delay);
    };

    timer = setTimeout(poll, POLL_INTERVALS_MS[0]);
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [screen, orderId, applyState]);

  const handleStart = useCallback(async () => {
    setPhoneError(null);
    if (!isValidPhone(normalisedPhone)) {
      setPhoneError('Enter a valid number, e.g. 0712345678 or 255712345678');
      return;
    }
    setScreen('starting');
    setErrorMessage(null);
    try {
      const next = await initiatePayment(orderId, normalisedPhone);
      applyState(next);
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : 'Payment could not be started.');
      setScreen('idle');
    }
  }, [normalisedPhone, orderId, applyState]);

  const handleVerify = useCallback(async () => {
    setErrorMessage(null);
    try {
      const next = await verifyPayment(orderId);
      applyState(next);
    } catch (error: unknown) {
      setErrorMessage(
        error instanceof Error ? error.message : 'Could not reach ClickPesa. Try again.',
      );
    }
  }, [orderId, applyState]);

  const handleRetry = useCallback(() => {
    setErrorMessage(null);
    setRawPhone('');
    setPhoneError(null);
    setState(null);
    setScreen('idle');
  }, []);

  /**
   * Resend the USSD push to the SAME phone number already entered.
   * Does NOT reset the form — user does not need to re-enter their number.
   * Works whether the current state is PENDING or FAILED (backend expires
   * any old PENDING attempt and creates a fresh one automatically).
   */
  const [resending, setResending] = useState(false);
  const handleResend = useCallback(async () => {
    setErrorMessage(null);
    setResending(true);
    try {
      const next = await initiatePayment(orderId, normalisedPhone);
      applyState(next);
    } catch (error: unknown) {
      setErrorMessage(
        error instanceof Error ? error.message : 'Could not resend. Please try again.',
      );
    } finally {
      setResending(false);
    }
  }, [normalisedPhone, orderId, applyState]);

  // ─── Loading ────────────────────────────────────────────────────────────────
  if (screen === 'loading') {
    return (
      <View style={styles.fullCenter}>
        <ActivityIndicator size="large" color={colors.primary} />
        <Text style={styles.loadingText}>Loading payment details…</Text>
      </View>
    );
  }

  // ─── Main render ────────────────────────────────────────────────────────────
  return (
    <SafeAreaView edges={['bottom']} style={styles.safe}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={styles.flex}
      >
        <ScrollView
          contentContainerStyle={styles.scroll}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >

          {/* ── Amount Header Card ─────────────────────────────────────────── */}
          <View style={styles.amountCard}>
            <View style={styles.amountCardTop}>
              <Text style={styles.amountCardLabel}>TOTAL PAYMENT DUE</Text>
              <View style={styles.amountRow}>
                <Text style={styles.amountCurrency}>TZS</Text>
                <Text style={styles.amountValue}>
                  {orderTotal != null
                    ? Number(orderTotal).toLocaleString()
                    : '—'}
                </Text>
              </View>
              {orderStatusLabel ? (
                <View style={styles.statusPill}>
                  <View style={styles.statusDot} />
                  <Text style={styles.statusPillText}>{orderStatusLabel}</Text>
                </View>
              ) : null}
            </View>
            <View style={styles.amountCardBottom}>
              <Text style={styles.securedText}>🔒 Secured by ClickPesa</Text>
            </View>
          </View>

          {/* ── IDLE: Phone Entry ──────────────────────────────────────────── */}
          {screen === 'idle' ? (
            <Animated.View
              style={[
                styles.section,
                { opacity: fadeAnim, transform: [{ translateY: slideAnim }] },
              ]}
            >
              {/* Header */}
              <View style={styles.methodHeader}>
                <View style={styles.methodIconWrap}>
                  <Text style={styles.methodIcon}>📱</Text>
                </View>
                <View style={styles.methodInfo}>
                  <Text style={styles.methodTitle}>Mobile Money Payment</Text>
                  <Text style={styles.methodSubtitle}>
                    Enter your number to receive a USSD prompt
                  </Text>
                </View>
              </View>

              {/* Instruction */}
              <Text style={styles.instructionText}>
                Enter the mobile money number linked to your account. A USSD
                payment request will be sent to your phone — confirm it with
                your PIN.
              </Text>

              {/* Network chips */}
              {/* Network is detected server-side via ClickPesa's preview and
                  returned in the payment's network_channel — no client-side
                  number guessing (which incorrectly forced M-Pesa). */}

              {/* Phone input */}
              <View style={styles.inputWrap}>
                <Text style={styles.inputLabel}>Mobile money number</Text>
                <View style={[styles.phoneInputRow, phoneError ? styles.phoneInputError : null]}>
                  <View style={styles.prefixBox}>
                    <Text style={styles.prefixFlag}>🇹🇿</Text>
                    <Text style={styles.prefixText}>+255</Text>
                  </View>
                  <View style={styles.inputDivider} />
                  <RNTextInput
                    style={styles.phoneInput}
                    value={rawPhone}
                    onChangeText={(v) => {
                      setRawPhone(v.replace(/[^0-9]/g, ''));
                      setPhoneError(null);
                      setErrorMessage(null);
                    }}
                    placeholder="0712 345 678  or  255712345678"
                    placeholderTextColor={colors.disabled}
                    keyboardType="phone-pad"
                    maxLength={13}
                    returnKeyType="done"
                    onSubmitEditing={() => void handleStart()}
                  />
                </View>
                {phoneError ? (
                  <Text style={styles.fieldError}>{phoneError}</Text>
                ) : rawPhone.length > 0 ? (
                  <View style={styles.phoneInfoRow}>
                    <Text style={styles.previewText}>
                      Will send to: <Text style={styles.previewNum}>{normalisedPhone}</Text>
                    </Text>
                  </View>
                ) : null}
              </View>

              {/* How it works */}
              <View style={styles.stepsCard}>
                <Text style={styles.stepsTitle}>How it works</Text>
                {[
                  'You tap "Pay Now" below',
                  'Your phone receives a USSD prompt',
                  'Enter your mobile money PIN',
                  'Payment confirmed automatically',
                ].map((step, i) => (
                  <View key={i} style={styles.stepRow}>
                    <View style={styles.stepBadge}>
                      <Text style={styles.stepNumber}>{i + 1}</Text>
                    </View>
                    <Text style={styles.stepText}>{step}</Text>
                  </View>
                ))}
              </View>

              {errorMessage ? (
                <View style={styles.errorBanner}>
                  <Text style={styles.errorBannerText}>⚠ {errorMessage}</Text>
                </View>
              ) : null}

              <Button
                title="Pay Now"
                onPress={() => void handleStart()}
                style={styles.payBtn}
              />
            </Animated.View>
          ) : null}

          {/* ── STARTING ──────────────────────────────────────────────────── */}
          {screen === 'starting' ? (
            <View style={styles.centeredSection}>
              <View style={styles.spinnerWrap}>
                <ActivityIndicator size="large" color={colors.primary} />
              </View>
              <Text style={styles.methodTitle}>Contacting ClickPesa…</Text>
              <Text style={styles.instructionText}>
                Sending USSD push request. This takes just a moment.
              </Text>
            </View>
          ) : null}

          {/* ── PENDING ───────────────────────────────────────────────────── */}
          {screen === 'pending' ? (
            <View style={styles.section}>
              <View style={styles.centeredSection}>
                <Animated.View
                  style={[styles.pulseRing, { transform: [{ scale: pulseAnim }] }]}
                >
                  <View style={styles.pulseInner}>
                    <Text style={styles.pulseEmoji}>📲</Text>
                  </View>
                </Animated.View>
                <Text style={styles.methodTitle}>Check your phone!</Text>
                <Text style={styles.instructionText}>
                  A USSD payment prompt has been sent to{' '}
                  <Text style={styles.highlight}>{normalisedPhone || 'your number'}</Text>.{'\n'}
                  Enter your mobile money PIN to confirm.
                </Text>
                {(() => {
                  const channel = state?.payment?.network_channel;
                  const display = channel ? formatChannel(channel) : null;
                  if (display) {
                    return (
                      <View style={[styles.networkChannelBanner, { backgroundColor: display.color + '12', borderColor: display.color + '30' }]}>
                        <View style={[styles.networkChannelDot, { backgroundColor: display.color }]} />
                        <Text style={[styles.networkChannelText, { color: display.color }]}>
                          Detected: {display.label}
                        </Text>
                      </View>
                    );
                  }
                  return null;
                })()}
              </View>

              <View style={styles.stepsCard}>
                <Text style={styles.stepsTitle}>What to do now</Text>
                {[
                  'Wait for the USSD pop-up on your phone',
                  'Select "Pay" or press 1',
                  'Enter your mobile money PIN',
                  'Wait — this page updates automatically',
                ].map((step, i) => (
                  <View key={i} style={styles.stepRow}>
                    <View style={styles.stepBadge}>
                      <Text style={styles.stepNumber}>{i + 1}</Text>
                    </View>
                    <Text style={styles.stepText}>{step}</Text>
                  </View>
                ))}
              </View>

              <Button
                title="I've paid — verify now"
                variant="secondary"
                onPress={() => void handleVerify()}
              />

              {/* ── Retry button — re-sends USSD without clearing phone ── */}
              <TouchableOpacity
                style={[styles.retryBtn, resending && styles.retryBtnBusy]}
                activeOpacity={0.75}
                disabled={resending}
                onPress={() => void handleResend()}
              >
                {resending ? (
                  <ActivityIndicator size="small" color={colors.primary} />
                ) : (
                  <Text style={styles.retryBtnText}>🔄  Retry Payment — Send Again</Text>
                )}
              </TouchableOpacity>

              <Text style={styles.retryHint}>
                Prompt dismissed or didn't arrive? Tap above to resend instantly
                to <Text style={styles.highlight}>{normalisedPhone || 'your number'}</Text>.
              </Text>

              {errorMessage ? (
                <View style={styles.errorBanner}>
                  <Text style={styles.errorBannerText}>⚠ {errorMessage}</Text>
                </View>
              ) : null}
            </View>
          ) : null}

          {/* ── FAILED ────────────────────────────────────────────────────── */}
          {screen === 'failed' ? (
            <View style={styles.section}>
              <View style={styles.centeredSection}>
                <View style={[styles.resultCircle, styles.failedCircle]}>
                  <Text style={styles.resultCircleText}>✗</Text>
                </View>
                <Text style={[styles.methodTitle, { color: colors.error }]}>
                  Payment Not Confirmed
                </Text>
                <Text style={styles.instructionText}>
                  ClickPesa reported {state?.payment?.status_label ?? 'a problem with your payment'}.{' '}
                  You can check the status again — it may still complete — or start a new attempt.
                </Text>
              </View>

              {/* Primary action: resend to same number — no restrictions */}
              <TouchableOpacity
                style={[styles.retryBtn, resending && styles.retryBtnBusy]}
                activeOpacity={0.75}
                disabled={resending}
                onPress={() => void handleResend()}
              >
                {resending ? (
                  <ActivityIndicator size="small" color={colors.primary} />
                ) : (
                  <Text style={styles.retryBtnText}>🔄  Retry Payment — Send Again</Text>
                )}
              </TouchableOpacity>

              <Text style={styles.retryHint}>
                This will resend the USSD prompt to{' '}
                <Text style={styles.highlight}>{normalisedPhone || 'your number'}</Text>{' '}
                immediately — no limit on retries.
              </Text>

              <Button
                title="Check status again"
                variant="secondary"
                onPress={() => void handleVerify()}
                style={styles.topGap}
              />
              <Button
                title="Change phone number"
                variant="secondary"
                onPress={handleRetry}
                style={styles.topGap}
              />

              {errorMessage ? (
                <View style={styles.errorBanner}>
                  <Text style={styles.errorBannerText}>⚠ {errorMessage}</Text>
                </View>
              ) : null}
            </View>
          ) : null}

        </ScrollView>
      </KeyboardAvoidingView>

      {/* ── Success Modal (auto-closes after 2.5 s) ───────────────────────── */}
      <Modal visible={showSuccess} transparent animationType="fade" statusBarTranslucent>
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <View style={[styles.resultCircle, styles.successCircle]}>
              <Text style={styles.resultCircleText}>✓</Text>
            </View>
            <Text style={styles.modalTitle}>Payment Received!</Text>
            {(() => {
              const channel = state?.payment?.network_channel;
              const display = channel ? formatChannel(channel) : null;
              if (display) {
                return (
                  <View style={[styles.networkChannelBanner, { backgroundColor: display.color + '12', borderColor: display.color + '30' }]}>
                    <View style={[styles.networkChannelDot, { backgroundColor: display.color }]} />
                    <Text style={[styles.networkChannelText, { color: display.color }]}>
                      Paid via {display.label}
                    </Text>
                  </View>
                );
              }
              return null;
            })()}
            <Text style={styles.modalBody}>
              ClickPesa has confirmed your payment. Your order is now being processed. Wait for delivery.
            </Text>
            <View style={styles.modalFooter}>
              <ActivityIndicator size="small" color={colors.success} />
              <Text style={styles.modalFooterText}>Returning to your order…</Text>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

// ─── Styles ──────────────────────────────────────────────────────────────────
const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  flex: { flex: 1 },
  fullCenter: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background,
    gap: spacing.md,
  },
  loadingText: { ...typography.label, marginTop: spacing.xs },
  scroll: {
    padding: spacing.lg,
    gap: spacing.xl,
    paddingBottom: 40,
  },

  // ── Amount card ────────────────────────────────────────────────────────────
  amountCard: {
    backgroundColor: colors.primary,
    borderRadius: radii.lg,
    overflow: 'hidden',
    shadowColor: colors.primary,
    shadowOpacity: 0.35,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 8 },
    elevation: 8,
  },
  amountCardTop: {
    paddingTop: spacing.xl,
    paddingHorizontal: spacing.xl,
    paddingBottom: spacing.lg,
    alignItems: 'center',
    gap: spacing.sm,
  },
  amountCardBottom: {
    backgroundColor: 'rgba(0,0,0,0.18)',
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.xl,
    alignItems: 'center',
  },
  amountCardLabel: {
    color: 'rgba(255,255,255,0.7)',
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1.5,
  },
  amountRow: { flexDirection: 'row', alignItems: 'flex-end', gap: spacing.xs },
  amountCurrency: {
    color: 'rgba(255,255,255,0.85)',
    fontSize: 18,
    fontWeight: '600',
    paddingBottom: 4,
  },
  amountValue: {
    color: '#FFFFFF',
    fontSize: 44,
    fontWeight: '800',
    letterSpacing: -1,
  },
  statusPill: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255,255,255,0.18)',
    borderRadius: radii.round,
    paddingHorizontal: spacing.md,
    paddingVertical: 4,
    gap: spacing.xs,
  },
  statusDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: '#A5F3C7',
  },
  statusPillText: { color: '#FFFFFF', fontSize: 12, fontWeight: '600' },
  securedText: { color: 'rgba(255,255,255,0.65)', fontSize: 12, fontWeight: '500' },

  // ── Section layouts ────────────────────────────────────────────────────────
  section: { gap: spacing.lg },
  centeredSection: { alignItems: 'center', gap: spacing.md },
  methodHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  methodIconWrap: {
    width: 46,
    height: 46,
    borderRadius: 23,
    backgroundColor: '#E8F5F0',
    alignItems: 'center',
    justifyContent: 'center',
  },
  methodIcon: { fontSize: 24 },
  methodInfo: { flex: 1 },
  methodTitle: { ...typography.body, fontWeight: '700', fontSize: 16 },
  methodSubtitle: { ...typography.label, marginTop: 2 },

  instructionText: {
    ...typography.body,
    color: colors.textSecondary,
    lineHeight: 22,
    textAlign: 'center',
  },
  highlight: { color: colors.primary, fontWeight: '700' },

  // ── Phone input ────────────────────────────────────────────────────────────
  inputWrap: { gap: spacing.xs },
  inputLabel: { ...typography.label, fontWeight: '600', color: colors.text, marginBottom: 2 },
  phoneInputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderWidth: 1.5,
    borderColor: colors.border,
    borderRadius: radii.md,
    overflow: 'hidden',
    height: 54,
  },
  phoneInputError: { borderColor: colors.error },
  prefixBox: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.md,
    gap: spacing.xs,
    backgroundColor: '#F0F9F5',
    height: '100%',
  },
  prefixFlag: { fontSize: 18 },
  prefixText: { color: colors.primary, fontWeight: '700', fontSize: 14 },
  inputDivider: { width: 1, height: '60%', backgroundColor: colors.border },
  phoneInput: {
    flex: 1,
    paddingHorizontal: spacing.md,
    fontSize: 16,
    color: colors.text,
    fontWeight: '600',
    letterSpacing: 0.5,
    height: '100%',
  },
  fieldError: { color: colors.error, fontSize: 12, marginTop: 2 },
  previewText: { color: colors.textSecondary, fontSize: 12 },
  previewNum: { color: colors.primary, fontWeight: '700' },
  phoneInfoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
    flexWrap: 'wrap',
  },
  networkChannelBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    borderWidth: 1,
    borderRadius: radii.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    marginTop: spacing.xs,
  },
  networkChannelDot: { width: 8, height: 8, borderRadius: 4 },
  networkChannelText: { fontSize: 13, fontWeight: '700' },

  // ── Steps card ─────────────────────────────────────────────────────────────
  stepsCard: {
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    padding: spacing.lg,
    gap: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  stepsTitle: { ...typography.body, fontWeight: '700', marginBottom: spacing.xs - 4 },
  stepRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  stepBadge: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepNumber: { color: '#FFFFFF', fontSize: 13, fontWeight: '700' },
  stepText: { ...typography.body, color: colors.textSecondary, flex: 1, lineHeight: 20 },

  // ── Error banner ───────────────────────────────────────────────────────────
  errorBanner: {
    backgroundColor: colors.errorSurface,
    borderRadius: radii.sm,
    padding: spacing.md,
    borderLeftWidth: 3,
    borderLeftColor: colors.error,
  },
  errorBannerText: { color: colors.error, fontSize: 13, lineHeight: 18 },

  payBtn: { marginTop: spacing.xs },
  topGap: { marginTop: spacing.sm },

  // ── Spinner wrap ───────────────────────────────────────────────────────────
  spinnerWrap: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: '#E8F5F0',
    alignItems: 'center',
    justifyContent: 'center',
  },

  // ── Pulse animation ────────────────────────────────────────────────────────
  pulseRing: {
    width: 110,
    height: 110,
    borderRadius: 55,
    backgroundColor: 'rgba(11,110,79,0.10)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  pulseInner: {
    width: 78,
    height: 78,
    borderRadius: 39,
    backgroundColor: 'rgba(11,110,79,0.18)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  pulseEmoji: { fontSize: 34 },

  // ── Result circles ─────────────────────────────────────────────────────────
  resultCircle: {
    width: 84,
    height: 84,
    borderRadius: 42,
    alignItems: 'center',
    justifyContent: 'center',
  },
  successCircle: { backgroundColor: '#E8F5E9' },
  failedCircle: { backgroundColor: colors.errorSurface },
  resultCircleText: { fontSize: 38, fontWeight: '700', color: colors.text },

  // ── Success Modal ──────────────────────────────────────────────────────────
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.6)',
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.xl,
  },
  modalCard: {
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    padding: spacing.xxl,
    alignItems: 'center',
    gap: spacing.lg,
    width: '100%',
    shadowColor: '#000',
    shadowOpacity: 0.25,
    shadowRadius: 24,
    shadowOffset: { width: 0, height: 12 },
    elevation: 12,
  },
  modalTitle: {
    fontSize: 22,
    fontWeight: '800',
    color: colors.success,
    textAlign: 'center',
  },
  modalBody: {
    ...typography.body,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 22,
  },
  modalFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginTop: spacing.xs,
  },
  modalFooterText: { ...typography.label },

  // ── Retry button styles ───────────────────────────────────────────────────
  retryBtn: {
    backgroundColor: colors.primary,
    borderRadius: radii.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    alignItems: 'center',
    justifyContent: 'center',
    marginVertical: spacing.xs,
  },
  retryBtnBusy: {
    opacity: 0.7,
  },
  retryBtnText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 15,
  },
  retryHint: {
    ...typography.label,
    textAlign: 'center',
    color: colors.textSecondary,
    fontSize: 12,
  },
});
