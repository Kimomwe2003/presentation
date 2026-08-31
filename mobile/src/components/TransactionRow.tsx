import { StyleSheet, Text, View } from 'react-native';

import type { LedgerTransaction } from '../api/types';
import { colors, spacing, typography } from '../theme';
import { formatPrice, formatRelativeTime } from '../utils/format';
import Card from './Card';

export default function TransactionRow({ tx }: { tx: LedgerTransaction }) {
  const isCredit = !tx.amount.startsWith('-');
  const sign = isCredit ? '+' : '−';
  const abs = tx.amount.replace('-', '');

  return (
    <Card style={styles.txCard}>
      <View style={styles.txRow}>
        <View style={styles.txInfo}>
          <Text style={styles.txType}>{tx.type_label}</Text>
          <Text style={styles.txMeta} numberOfLines={1}>
            {tx.description || tx.reference || 'Ledger entry'} · {formatRelativeTime(tx.created_at)}
          </Text>
        </View>
        <Text style={[styles.txAmount, isCredit ? styles.amountPositive : styles.amountNegative]}>
          {sign}
          {formatPrice(abs)}
        </Text>
      </View>
    </Card>
  );
}

const styles = StyleSheet.create({
  txCard: {
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  txRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.md,
  },
  txInfo: {
    flex: 1,
    gap: 2,
  },
  txType: {
    ...typography.body,
    fontWeight: '600',
  },
  txMeta: {
    ...typography.label,
  },
  txAmount: {
    ...typography.body,
    fontWeight: '700',
  },
  amountPositive: {
    color: colors.success,
  },
  amountNegative: {
    color: colors.error,
  },
});
