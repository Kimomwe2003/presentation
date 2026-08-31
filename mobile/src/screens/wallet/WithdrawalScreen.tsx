import { useCallback, useEffect, useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { getErrorMessage } from '../../api/errors';
import type { WithdrawalProvider } from '../../api/types';
import { fetchWalletBalance, requestWithdrawal } from '../../api/wallet';
import Button from '../../components/Button';
import Card from '../../components/Card';
import Chip from '../../components/Chip';
import EmptyState from '../../components/EmptyState';
import ErrorState from '../../components/ErrorState';
import LoadingSpinner from '../../components/LoadingSpinner';
import TextInput from '../../components/TextInput';
import { useToast } from '../../context/ToastContext';
import type { RootStackParamList } from '../../navigation/types';
import { colors, spacing, typography } from '../../theme';
import { formatPrice } from '../../utils/format';

type Props = NativeStackScreenProps<RootStackParamList, 'Withdraw'>;

const PROVIDERS: { value: WithdrawalProvider; label: string }[] = [
  { value: 'mpesa', label: 'M-Pesa' },
  { value: 'tigo_pesa', label: 'Tigo Pesa' },
  { value: 'airtel_money', label: 'Airtel Money' },
  { value: 'halopesa', label: 'Halopesa' },
];

const MIN_AMOUNT = 500;

export default function WithdrawalScreen({ navigation }: Props) {
  const { showToast } = useToast();
  const [balance, setBalance] = useState<string | null>(null);
  const [amount, setAmount] = useState('');
  const [provider, setProvider] = useState<WithdrawalProvider>('mpesa');
  const [number, setNumber] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const summary = await fetchWalletBalance();
      setBalance(summary.balance);
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      await Promise.resolve();
      if (cancelled) return;
      await load();
    })();
    return () => {
      cancelled = true;
    };
  }, [load]);

  const handleSubmit = useCallback(async () => {
    const parsed = Number(amount);
    if (!amount || Number.isNaN(parsed) || parsed < MIN_AMOUNT) {
      setError(`Minimum withdrawal is TZS ${MIN_AMOUNT.toLocaleString()}.`);
      return;
    }
    if (balance != null && parsed > Number(balance)) {
      setError('Amount exceeds your available balance.');
      return;
    }
    if (!number.trim()) {
      setError('Enter your mobile money number.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await requestWithdrawal({
        amount: amount,
        provider,
        mobile_money_number: number.trim(),
      });
      showToast('Withdrawal request submitted.', { type: 'success' });
      navigation.goBack();
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setSubmitting(false);
    }
  }, [amount, balance, number, provider, showToast, navigation]);

  if (loading) {
    return <LoadingSpinner label="Loading your wallet…" />;
  }

  if (error && balance == null) {
    return <ErrorState message={error} onRetry={() => void load()} />;
  }

  return (
    <SafeAreaView edges={['bottom']} style={styles.safe}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={styles.flex}
      >
        <ScrollView contentContainerStyle={styles.content}>
          <Card style={styles.balanceCard}>
            <Text style={styles.balanceLabel}>Available to withdraw</Text>
            <Text style={styles.balanceValue}>TZS {formatPrice(balance ?? '0')}</Text>
          </Card>

          <Card style={styles.form}>
            <TextInput
              label="Amount (TZS)"
              value={amount}
              onChangeText={(value) => {
                setAmount(value.replace(/[^0-9.]/g, ''));
                setError(null);
              }}
              placeholder={`Minimum ${MIN_AMOUNT}`}
              keyboardType="decimal-pad"
            />

            <Text style={styles.label}>Provider</Text>
            <View style={styles.chipRow}>
              {PROVIDERS.map((p) => (
                <Chip
                  key={p.value}
                  label={p.label}
                  selected={provider === p.value}
                  onPress={() => setProvider(p.value)}
                />
              ))}
            </View>

            <TextInput
              label="Mobile money number"
              value={number}
              onChangeText={(value) => {
                setNumber(value.replace(/[^0-9]/g, ''));
                setError(null);
              }}
              placeholder="07XXXXXXXX"
              keyboardType="phone-pad"
              maxLength={12}
            />

            {error ? <Text style={styles.error}>{error}</Text> : null}
          </Card>

          {Number(balance ?? 0) <= 0 ? (
            <EmptyState
              icon="wallet-outline"
              title="No balance to withdraw"
              message="You’ll be able to request a payout once completed sales credit your wallet."
            />
          ) : (
            <Button
              title="Request withdrawal"
              loading={submitting}
              onPress={() => void handleSubmit()}
            />
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: colors.background,
  },
  flex: {
    flex: 1,
  },
  content: {
    padding: spacing.lg,
    gap: spacing.md,
  },
  balanceCard: {
    alignItems: 'center',
    paddingVertical: spacing.xl,
  },
  balanceLabel: {
    ...typography.label,
  },
  balanceValue: {
    ...typography.title,
    color: colors.primary,
    marginTop: spacing.xs,
  },
  form: {
    gap: spacing.md,
  },
  label: {
    ...typography.label,
  },
  chipRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  error: {
    ...typography.label,
    color: colors.error,
  },
});
