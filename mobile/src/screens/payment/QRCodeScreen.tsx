import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Share,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import QRCode from 'react-native-qrcode-svg';

import { fetchPaymentStatus } from '../../api/payments';
import Button from '../../components/Button';
import type { RootStackParamList } from '../../navigation/types';
import { colors, radii, spacing, typography } from '../../theme';

type Props = NativeStackScreenProps<RootStackParamList, 'QRCode'>;

export default function QRCodeScreen({ route }: Props) {
  const { orderId } = route.params;
  const [amount, setAmount] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    fetchPaymentStatus(orderId)
      .then((state) => {
        if (!active) return;
        setAmount(state.payment?.amount ?? state.order.total ?? null);
      })
      .catch(() => {})
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [orderId]);

  const handleShare = async () => {
    try {
      await Share.share({
        message: `Pay for order #${orderId} on ReuseHub. Open the app and scan this QR code, or pay directly.`,
      });
    } catch {}
  };

  return (
    <SafeAreaView edges={['bottom']} style={styles.safe}>
      <View style={styles.container}>
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.title}>Scan to Pay</Text>
          <Text style={styles.subtitle}>
            Show this QR code to the buyer, or share the order reference.
          </Text>
        </View>

        {/* QR Code */}
        <View style={styles.qrWrap}>
          {loading ? (
            <View style={styles.qrPlaceholder}>
              <ActivityIndicator size="large" color={colors.primary} />
            </View>
          ) : (
            <View style={styles.qrCard}>
              <QRCode
                value={`reusehub-order:${orderId}`}
                size={220}
                backgroundColor="#FFFFFF"
                color="#0B6E4F"
                logoMargin={2}
              />
            </View>
          )}
        </View>

        {/* Order info */}
        <View style={styles.infoCard}>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Order ID</Text>
            <Text style={styles.infoValue}>#{orderId}</Text>
          </View>
          {amount != null ? (
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Amount</Text>
              <Text style={styles.infoValue}>
                TZS {Number(amount).toLocaleString()}
              </Text>
            </View>
          ) : null}
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Format</Text>
            <Text style={styles.infoValue}>reusehub-order:{orderId}</Text>
          </View>
        </View>

        {/* Instructions */}
        <View style={styles.stepsCard}>
          <Text style={styles.stepsTitle}>How it works</Text>
          {[
            'Buyer opens the ReuseHub app',
            'Taps "Scan QR" on the home screen',
            'Points camera at this QR code',
            'Enters their mobile money number to pay',
          ].map((step, i) => (
            <View key={i} style={styles.stepRow}>
              <View style={styles.stepBadge}>
                <Text style={styles.stepNumber}>{i + 1}</Text>
              </View>
              <Text style={styles.stepText}>{step}</Text>
            </View>
          ))}
        </View>

        {/* Share button */}
        <Button
          title="Share Order Reference"
          variant="secondary"
          onPress={handleShare}
        />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  container: {
    flex: 1,
    padding: spacing.xl,
    gap: spacing.xl,
    alignItems: 'center',
  },
  header: { alignItems: 'center', gap: spacing.sm },
  title: { ...typography.title, textAlign: 'center' },
  subtitle: {
    ...typography.body,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 21,
  },

  qrWrap: { alignItems: 'center' },
  qrPlaceholder: {
    width: 240,
    height: 240,
    borderRadius: radii.lg,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: colors.border,
  },
  qrCard: {
    padding: spacing.xl,
    borderRadius: radii.lg,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    shadowColor: '#000',
    shadowOpacity: 0.08,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
    elevation: 4,
  },

  infoCard: {
    width: '100%',
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    padding: spacing.lg,
    gap: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  infoLabel: { ...typography.label, fontWeight: '600', color: colors.textSecondary },
  infoValue: { ...typography.body, fontWeight: '700' },

  stepsCard: {
    width: '100%',
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
    width: 26,
    height: 26,
    borderRadius: 13,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepNumber: { color: '#FFFFFF', fontSize: 12, fontWeight: '700' },
  stepText: { ...typography.body, color: colors.textSecondary, flex: 1, lineHeight: 20 },
});
