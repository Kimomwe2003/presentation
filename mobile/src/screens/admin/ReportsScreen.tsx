import { useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { fetchAdminReports } from '../../api/admin';
import type { AdminReportSummary } from '../../api/types';
import Card from '../../components/Card';
import type { RootStackParamList } from '../../navigation/types';
import { colors, spacing, typography } from '../../theme';

type Props = NativeStackScreenProps<RootStackParamList, 'Reports'>;

export default function ReportsScreen(_props: Props) {
  const [data, setData] = useState<AdminReportSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const report = await fetchAdminReports(30);
        if (!cancelled) setData(report);
      } catch {
        if (!cancelled) setError('Could not load reports.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  if (error || !data) {
    return (
      <View style={styles.center}>
        <Text style={styles.error}>{error ?? 'Nothing to show.'}</Text>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.subtitle}>Last {data.days} days</Text>

      <ReportSection title="Transaction volume (TZS)" rows={data.transaction_volume} />
      <ReportSection title="Fee revenue (TZS)" rows={data.fee_revenue} />
      <ReportSection title="New users" rows={data.new_users} countMode />
    </ScrollView>
  );
}

interface Row {
  date: string;
  total?: string;
  count?: number;
}

function ReportSection({
  title,
  rows,
  countMode = false,
}: {
  title: string;
  rows: Row[];
  countMode?: boolean;
}) {
  return (
    <Card style={styles.section}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {rows.length === 0 ? (
        <Text style={styles.empty}>No data in this period.</Text>
      ) : (
        <View style={styles.table}>
          {rows.map((row) => (
            <View key={String(row.date)} style={styles.tableRow}>
              <Text style={styles.tableDate}>
                {new Date(String(row.date)).toLocaleDateString()}
              </Text>
              <Text style={styles.tableValue}>
                {countMode ? String(row.count ?? 0) : Number(row.total ?? 0).toLocaleString()}
              </Text>
            </View>
          ))}
        </View>
      )}
    </Card>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.lg,
    gap: spacing.lg,
  },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background,
    padding: spacing.lg,
  },
  error: {
    ...typography.body,
    color: colors.error,
    textAlign: 'center',
  },
  subtitle: {
    ...typography.label,
  },
  section: {
    gap: spacing.sm,
  },
  sectionTitle: {
    ...typography.subtitle,
    fontWeight: '700',
  },
  table: {
    gap: 2,
  },
  tableRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 2,
  },
  tableDate: {
    ...typography.body,
    fontSize: 13,
    color: colors.textSecondary,
  },
  tableValue: {
    ...typography.body,
    fontSize: 13,
    fontWeight: '600',
  },
  empty: {
    ...typography.label,
  },
});
