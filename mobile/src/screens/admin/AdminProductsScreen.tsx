import { useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { fetchAdminProducts, removeProduct } from '../../api/admin';
import { getErrorMessage } from '../../api/errors';
import type { AdminProduct, Paginated } from '../../api/types';
import Badge from '../../components/Badge';
import Button from '../../components/Button';
import TextInput from '../../components/TextInput';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import type { RootStackParamList } from '../../navigation/types';
import { colors, radii, spacing, typography } from '../../theme';

type Props = NativeStackScreenProps<RootStackParamList, 'AdminProducts'>;

export default function AdminProductsScreen(_props: Props) {
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebouncedValue(search, 300);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Paginated<AdminProduct> | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Moderation modal state.
  const [target, setTarget] = useState<AdminProduct | null>(null);
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [removeError, setRemoveError] = useState<string | null>(null);

  async function load(nextPage = 1, replace = true) {
    try {
      if (replace) setLoading(true);
      else setLoadingMore(true);
      const result = await fetchAdminProducts({ search: debouncedSearch, page: nextPage });
      if (replace) setData(result);
      else
        setData((prev) =>
          prev ? { ...result, results: [...prev.results, ...result.results] } : result,
        );
      setError(null);
    } catch {
      setError('Could not load products.');
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }

  const [searchApplied, setSearchApplied] = useState<string>('');
  if (searchApplied !== debouncedSearch) {
    setSearchApplied(debouncedSearch);
    setPage(1);
    load(1, true);
  }

  function loadMore() {
    const next = page + 1;
    if (data?.next) {
      setPage(next);
      load(next, false);
    }
  }

  async function confirmRemove() {
    if (!target || !reason.trim()) return;
    setSubmitting(true);
    setRemoveError(null);
    try {
      await removeProduct(target.id, reason.trim());
      setTarget(null);
      setReason('');
      await load(1, true);
    } catch (e) {
      setRemoveError(getErrorMessage(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <View style={styles.container}>
      <TextInput
        placeholder="Search by listing name, seller or category"
        value={search}
        onChangeText={setSearch}
        autoCapitalize="none"
      />

      {error ? <Text style={styles.error}>{error}</Text> : null}

      <FlatList
        data={data?.results ?? []}
        keyExtractor={(item) => String(item.id)}
        onEndReached={loadMore}
        onEndReachedThreshold={0.3}
        ListEmptyComponent={
          loading ? (
            <ActivityIndicator style={styles.center} color={colors.primary} />
          ) : (
            <Text style={styles.empty}>No products found.</Text>
          )
        }
        ListFooterComponent={loadingMore ? <ActivityIndicator color={colors.primary} /> : null}
        renderItem={({ item }) => (
          <View style={styles.productCard}>
            <View style={styles.productInfo}>
              <Text style={styles.productName}>{item.name}</Text>
              <Text style={styles.productMeta}>
                {item.seller.full_name} · TZS {Number(item.price).toLocaleString()}
              </Text>
              <View style={styles.badges}>
                <Badge
                  label={item.status}
                  variant={item.status === 'ACTIVE' ? 'success' : 'neutral'}
                />
                {item.review_count > 0 ? (
                  <Badge label={`★ ${item.average_rating ?? '—'} (${item.review_count})`} />
                ) : null}
              </View>
            </View>
            <Pressable
              onPress={() => {
                setTarget(item);
                setReason('');
                setRemoveError(null);
              }}
              style={({ pressed }) => [styles.removeBtn, pressed && styles.pressed]}
            >
              <Text style={styles.removeText}>Remove</Text>
            </Pressable>
          </View>
        )}
      />

      <Modal visible={target !== null} transparent animationType="fade">
        <View style={styles.modalBackdrop}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>Remove listing</Text>
            {target ? <Text style={styles.modalProduct}>{target.name}</Text> : null}
            <Text style={styles.label}>Reason (required)</Text>
            <TextInput
              value={reason}
              onChangeText={setReason}
              placeholder="e.g. scam listing, prohibited item"
              multiline
            />
            {removeError ? <Text style={styles.error}>{removeError}</Text> : null}
            <Button
              title="Confirm removal"
              variant="danger"
              loading={submitting}
              disabled={!reason.trim()}
              onPress={() => void confirmRemove()}
            />
            <Button
              title="Cancel"
              variant="secondary"
              disabled={submitting}
              onPress={() => setTarget(null)}
            />
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    padding: spacing.lg,
    gap: spacing.md,
  },
  error: {
    ...typography.label,
    color: colors.error,
  },
  center: {
    marginVertical: spacing.xl,
  },
  empty: {
    ...typography.label,
    textAlign: 'center',
    marginTop: spacing.xl,
  },
  productCard: {
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    padding: spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    marginBottom: spacing.sm,
  },
  productInfo: {
    flex: 1,
    gap: 2,
  },
  productName: {
    ...typography.body,
    fontWeight: '600',
  },
  productMeta: {
    ...typography.label,
  },
  badges: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginTop: 2,
  },
  removeBtn: {
    backgroundColor: colors.errorSurface,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  removeText: {
    color: colors.error,
    fontWeight: '600',
  },
  pressed: {
    opacity: 0.7,
  },
  modalBackdrop: {
    flex: 1,
    backgroundColor: colors.overlay,
    justifyContent: 'center',
    padding: spacing.lg,
  },
  modalCard: {
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    padding: spacing.lg,
    gap: spacing.md,
  },
  modalTitle: {
    ...typography.title,
    fontSize: 18,
  },
  modalProduct: {
    ...typography.body,
    color: colors.textSecondary,
  },
  label: {
    ...typography.label,
    fontWeight: '600',
  },
});
