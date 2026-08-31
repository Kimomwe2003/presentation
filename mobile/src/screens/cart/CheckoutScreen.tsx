/**
 * CheckoutScreen — Shipping details before ClickPesa payment.
 *
 * After placing the order, navigates DIRECTLY to PaymentScreen
 * so the user immediately enters their mobile money number.
 */
import { useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput as RNTextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { checkoutCart } from '../../api/cart';
import { getErrorMessage } from '../../api/errors';
import Button from '../../components/Button';
import { useToast } from '../../context/ToastContext';
import type { RootStackParamList } from '../../navigation/types';
import { colors, radii, spacing, typography } from '../../theme';

type Props = NativeStackScreenProps<RootStackParamList, 'Checkout'>;

export default function CheckoutScreen({ navigation }: Props) {
  const { showToast } = useToast();
  const [shippingAddress, setShippingAddress] = useState('');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isReady = shippingAddress.trim().length > 3;

  const handlePlaceOrder = async () => {
    if (!isReady) {
      setError('Please enter your shipping address.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const order = await checkoutCart({
        payment_method: 'card',
        shipping_address: {
          address: shippingAddress.trim(),
          phone_number: phoneNumber.trim(),
        },
      });
      showToast('Order placed — complete payment to confirm.', { type: 'success' });
      navigation.replace('Payment', { orderId: order.id });
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setSubmitting(false);
    }
  };

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

          {/* ── Progress bar ─────────────────────────────────────────────── */}
          <View style={styles.progressWrap}>
            <View style={styles.progressStep}>
              <View style={[styles.progressDot, styles.progressDotDone]}>
                <Text style={styles.progressDotText}>✓</Text>
              </View>
              <Text style={styles.progressLabelDone}>Cart</Text>
            </View>
            <View style={styles.progressLine} />
            <View style={styles.progressStep}>
              <View style={[styles.progressDot, styles.progressDotActive]}>
                <Text style={styles.progressDotText}>2</Text>
              </View>
              <Text style={styles.progressLabelActive}>Shipping</Text>
            </View>
            <View style={styles.progressLine} />
            <View style={styles.progressStep}>
              <View style={styles.progressDot}>
                <Text style={[styles.progressDotText, { color: colors.disabled }]}>3</Text>
              </View>
              <Text style={styles.progressLabel}>Payment</Text>
            </View>
          </View>

          {/* ── Header ───────────────────────────────────────────────────── */}
          <View>
            <Text style={styles.screenTitle}>Shipping Details</Text>
            <Text style={styles.screenSubtitle}>
              Your order is created from the items in your cart. After checkout
              you'll confirm payment with ClickPesa.
            </Text>
          </View>

          {/* ── Shipping address ─────────────────────────────────────────── */}
          <View style={styles.fieldGroup}>
            <View style={styles.fieldLabelRow}>
              <Text style={styles.fieldIcon}>📍</Text>
              <Text style={styles.fieldLabel}>Delivery Address</Text>
              <Text style={styles.required}>*</Text>
            </View>
            <RNTextInput
              style={[styles.textArea, !shippingAddress && styles.textAreaEmpty]}
              value={shippingAddress}
              onChangeText={(v) => {
                setShippingAddress(v);
                setError(null);
              }}
              placeholder="Street, area, district, city"
              placeholderTextColor={colors.disabled}
              multiline
              numberOfLines={3}
              textAlignVertical="top"
            />
          </View>

          {/* ── Phone (for delivery) ─────────────────────────────────────── */}
          <View style={styles.fieldGroup}>
            <View style={styles.fieldLabelRow}>
              <Text style={styles.fieldIcon}>📞</Text>
              <Text style={styles.fieldLabel}>Contact Number</Text>
              <Text style={styles.optional}>(optional)</Text>
            </View>
            <RNTextInput
              style={styles.textField}
              value={phoneNumber}
              onChangeText={(v) => {
                setPhoneNumber(v.replace(/[^0-9+\s-]/g, ''));
                setError(null);
              }}
              placeholder="07XXXXXXXX — for delivery updates"
              placeholderTextColor={colors.disabled}
              keyboardType="phone-pad"
            />
          </View>

          {/* ── What happens next ────────────────────────────────────────── */}
          <View style={styles.nextStepsCard}>
            <Text style={styles.nextStepsTitle}>What happens next?</Text>
            {[
              { icon: '📦', text: 'Your order is placed from your current cart' },
              { icon: '📱', text: 'You pay instantly with mobile money (ClickPesa)' },
              { icon: '🚚', text: 'Seller confirms and ships your items' },
            ].map((s, i) => (
              <View key={i} style={styles.nextRow}>
                <Text style={styles.nextIcon}>{s.icon}</Text>
                <Text style={styles.nextText}>{s.text}</Text>
              </View>
            ))}
          </View>

          {/* ── Error banner ─────────────────────────────────────────────── */}
          {error ? (
            <View style={styles.errorBanner}>
              <Text style={styles.errorText}>⚠ {error}</Text>
            </View>
          ) : null}

          {/* ── CTA ──────────────────────────────────────────────────────── */}
          <View style={styles.ctaWrap}>
            <Button
              title={submitting ? 'Placing order…' : 'Place Order & Pay'}
              loading={submitting}
              disabled={submitting || !isReady}
              onPress={() => void handlePlaceOrder()}
            />
            <Text style={styles.ctaNote}>
              You'll be taken directly to the payment step after placing your order.
            </Text>
          </View>

        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  flex: { flex: 1 },
  scroll: {
    padding: spacing.lg,
    gap: spacing.xl,
    paddingBottom: 40,
  },

  // ── Progress ───────────────────────────────────────────────────────────────
  progressWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 0,
    paddingVertical: spacing.sm,
  },
  progressStep: { alignItems: 'center', gap: 4 },
  progressLine: { flex: 1, height: 2, backgroundColor: colors.border, marginBottom: 16 },
  progressDot: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  progressDotDone: { backgroundColor: colors.success },
  progressDotActive: { backgroundColor: colors.primary },
  progressDotText: { color: '#FFFFFF', fontSize: 12, fontWeight: '700' },
  progressLabel: { ...typography.label, color: colors.disabled, fontSize: 11 },
  progressLabelDone: { ...typography.label, color: colors.success, fontSize: 11, fontWeight: '600' },
  progressLabelActive: { ...typography.label, color: colors.primary, fontSize: 11, fontWeight: '700' },

  // ── Header ─────────────────────────────────────────────────────────────────
  screenTitle: {
    fontSize: 24,
    fontWeight: '800',
    color: colors.text,
    marginBottom: spacing.xs,
  },
  screenSubtitle: {
    ...typography.body,
    color: colors.textSecondary,
    lineHeight: 22,
  },

  // ── Form fields ────────────────────────────────────────────────────────────
  fieldGroup: { gap: spacing.sm },
  fieldLabelRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  fieldIcon: { fontSize: 16 },
  fieldLabel: {
    ...typography.body,
    fontWeight: '700',
    color: colors.text,
  },
  required: {
    color: colors.error,
    fontWeight: '700',
    fontSize: 16,
  },
  optional: {
    ...typography.label,
    color: colors.textSecondary,
  },
  textArea: {
    backgroundColor: colors.surface,
    borderWidth: 1.5,
    borderColor: colors.border,
    borderRadius: radii.md,
    paddingHorizontal: spacing.md,
    paddingTop: spacing.md,
    paddingBottom: spacing.md,
    fontSize: 15,
    color: colors.text,
    minHeight: 88,
    lineHeight: 22,
  },
  textAreaEmpty: { borderColor: colors.border },
  textField: {
    backgroundColor: colors.surface,
    borderWidth: 1.5,
    borderColor: colors.border,
    borderRadius: radii.md,
    paddingHorizontal: spacing.md,
    height: 52,
    fontSize: 15,
    color: colors.text,
  },

  // ── Next steps ─────────────────────────────────────────────────────────────
  nextStepsCard: {
    backgroundColor: '#F0F9F5',
    borderRadius: radii.md,
    padding: spacing.lg,
    gap: spacing.md,
    borderWidth: 1,
    borderColor: '#C3E8D8',
  },
  nextStepsTitle: {
    ...typography.body,
    fontWeight: '700',
    color: colors.primaryDark,
    marginBottom: 2,
  },
  nextRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.md,
  },
  nextIcon: { fontSize: 18, marginTop: 1 },
  nextText: {
    ...typography.body,
    color: colors.text,
    flex: 1,
    lineHeight: 20,
  },

  // ── Error ──────────────────────────────────────────────────────────────────
  errorBanner: {
    backgroundColor: colors.errorSurface,
    borderRadius: radii.sm,
    padding: spacing.md,
    borderLeftWidth: 3,
    borderLeftColor: colors.error,
  },
  errorText: { color: colors.error, fontSize: 13, lineHeight: 18 },

  // ── CTA ────────────────────────────────────────────────────────────────────
  ctaWrap: { gap: spacing.sm },
  ctaNote: {
    ...typography.label,
    textAlign: 'center',
    color: colors.textSecondary,
    lineHeight: 18,
  },
});
