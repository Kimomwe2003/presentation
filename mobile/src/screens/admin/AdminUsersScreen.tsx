import { useState } from 'react';
import { ActivityIndicator, FlatList, Pressable, StyleSheet, Text, View } from 'react-native';
import { NativeStackScreenProps } from '@react-navigation/native-stack';

import { fetchAdminUsers } from '../../api/admin';
import type { AdminUser, Paginated } from '../../api/types';
import Badge from '../../components/Badge';
import TextInput from '../../components/TextInput';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import type { RootStackParamList } from '../../navigation/types';
import { colors, radii, spacing, typography } from '../../theme';

type Props = NativeStackScreenProps<RootStackParamList, 'AdminUsers'>;

export default function AdminUsersScreen({ navigation }: Props) {
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebouncedValue(search, 300);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Paginated<AdminUser> | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load(nextPage = 1, replace = true) {
    try {
      if (replace) setLoading(true);
      else setLoadingMore(true);
      const result = await fetchAdminUsers({ search: debouncedSearch, page: nextPage });
      if (replace) setData(result);
      else
        setData((prev) =>
          prev ? { ...result, results: [...prev.results, ...result.results] } : result,
        );
      setError(null);
    } catch {
      setError('Could not load users.');
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }

  // Reload when the debounced search changes.
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

  const onSearchChange = (text: string) => setSearch(text);

  return (
    <View style={styles.container}>
      <TextInput
        placeholder="Search by email, username or full name"
        value={search}
        onChangeText={onSearchChange}
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
            <Text style={styles.empty}>No users found.</Text>
          )
        }
        ListFooterComponent={loadingMore ? <ActivityIndicator color={colors.primary} /> : null}
        renderItem={({ item }) => (
          <Pressable
            onPress={() =>
              navigation.navigate('AdminUserDetail', { userId: item.id, email: item.email })
            }
            style={({ pressed }) => [styles.userCard, pressed && styles.pressed]}
          >
            <Text style={styles.userName}>{item.profile.full_name || item.email}</Text>
            <Text style={styles.userEmail}>{item.email}</Text>
            <View style={styles.badges}>
              {item.is_suspended ? <Badge label="Suspended" variant="danger" /> : null}
              {item.is_staff ? <Badge label="Staff" variant="primary" /> : null}
            </View>
          </Pressable>
        )}
      />
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
  userCard: {
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    padding: spacing.md,
    gap: 4,
    marginBottom: spacing.sm,
  },
  pressed: {
    opacity: 0.7,
  },
  userName: {
    ...typography.body,
    fontWeight: '600',
  },
  userEmail: {
    ...typography.label,
  },
  badges: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginTop: 2,
  },
});
