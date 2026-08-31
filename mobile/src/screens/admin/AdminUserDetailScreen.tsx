import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { NativeStackScreenProps } from '@react-navigation/native-stack';

import {
  activateUser,
  deleteUser,
  fetchAdminUserDetail,
  suspendUser,
  updateUser,
} from '../../api/admin';
import type { AdminRole, AdminUserDetail } from '../../api/types';
import Button from '../../components/Button';
import Card from '../../components/Card';
import TextInput from '../../components/TextInput';
import { useToast } from '../../context/ToastContext';
import type { RootStackParamList } from '../../navigation/types';
import { colors, radii, spacing, typography } from '../../theme';

type Props = NativeStackScreenProps<RootStackParamList, 'AdminUserDetail'>;

const ROLE_OPTIONS: { value: AdminRole; label: string }[] = [
  { value: 'BUYER', label: 'Buyer' },
  { value: 'SELLER', label: 'Seller' },
  { value: 'ADMIN', label: 'Admin' },
];

export default function AdminUserDetailScreen({ route, navigation }: Props) {
  const { userId } = route.params;
  const { showToast } = useToast();
  const [user, setUser] = useState<AdminUserDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const result = await fetchAdminUserDetail(userId);
        if (!cancelled) setUser(result);
      } catch {
        if (!cancelled) setError('Could not load this user.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId]);

  async function refresh() {
    try {
      setError(null);
      setActionError(null);
      setUser(await fetchAdminUserDetail(userId));
    } catch {
      setError('Could not load this user.');
    }
  }

  async function toggleSuspension() {
    if (!user) return;
    setBusy(true);
    setActionError(null);
    try {
      if (user.is_suspended) await activateUser(user.id);
      else await suspendUser(user.id);
      showToast(user.is_suspended ? 'Account reactivated.' : 'Account suspended.', {
        type: 'success',
      });
      await refresh();
    } catch {
      setActionError('That action could not be completed.');
    } finally {
      setBusy(false);
    }
  }

  async function handleSave() {
    if (!user) return;
    setBusy(true);
    setActionError(null);
    try {
      const updated = await updateUser(user.id, {
        email: form.email.trim(),
        full_name: form.full_name.trim(),
        phone_number: form.phone_number.trim() || null,
        address: form.address.trim(),
        role: form.role,
      });
      setUser(updated);
      setEditing(false);
      showToast('User updated.', { type: 'success' });
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : 'The user could not be updated.',
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    if (!user) return;
    if (!confirmDelete) {
      setConfirmDelete(true);
      setActionError(null);
      return;
    }
    setBusy(true);
    setActionError(null);
    try {
      await deleteUser(user.id);
      showToast('User deleted.', { type: 'success' });
      navigation.goBack();
    } catch {
      setActionError('The user could not be deleted.');
      setBusy(false);
      setConfirmDelete(false);
    }
  }

  const [form, setForm] = useState({
    email: '',
    full_name: '',
    phone_number: '',
    address: '',
    role: 'BUYER' as AdminRole,
  });

  useEffect(() => {
    if (user) {
      setForm({
        email: user.email,
        full_name: user.profile.full_name ?? '',
        phone_number: user.profile.phone_number ?? '',
        address: user.profile.address ?? '',
        role: ((user.profile as { role?: AdminRole }).role as AdminRole) ?? 'BUYER',
      });
    }
  }, [user]);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  if (error || !user) {
    return (
      <View style={styles.center}>
        <Text style={styles.error}>{error ?? 'Nothing to show.'}</Text>
        <Button title="Retry" onPress={() => void refresh()} />
      </View>
    );
  }

  if (editing) {
    return (
      <ScrollView style={styles.container}>
        <Card style={styles.card}>
          <Text style={styles.sectionTitle}>Edit account</Text>

          <TextInput
            label="Full name"
            value={form.full_name}
            onChangeText={(text) => setForm((f) => ({ ...f, full_name: text }))}
            placeholder="Jane Doe"
          />
          <TextInput
            label="Email"
            value={form.email}
            onChangeText={(text) => setForm((f) => ({ ...f, email: text }))}
            placeholder="user@example.com"
            autoCapitalize="none"
            keyboardType="email-address"
          />
          <TextInput
            label="Phone number"
            value={form.phone_number}
            onChangeText={(text) => setForm((f) => ({ ...f, phone_number: text }))}
            placeholder="+255 700 000 000"
            keyboardType="phone-pad"
          />
          <TextInput
            label="Address"
            value={form.address}
            onChangeText={(text) => setForm((f) => ({ ...f, address: text }))}
            placeholder="City, Country"
          />

          <Text style={styles.fieldLabel}>Role</Text>
          <View style={styles.roleRow}>
            {ROLE_OPTIONS.map((option) => {
              const active = form.role === option.value;
              return (
                <Pressable
                  key={option.value}
                  onPress={() => setForm((f) => ({ ...f, role: option.value }))}
                  style={[styles.rolePill, active && styles.rolePillActive]}
                >
                  <Text style={[styles.roleText, active && styles.roleTextActive]}>
                    {option.label}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </Card>

        {actionError ? <Text style={styles.error}>{actionError}</Text> : null}

        <Button title="Save changes" loading={busy} onPress={() => void handleSave()} />
        <Button
          title="Cancel"
          variant="secondary"
          disabled={busy}
          onPress={() => {
            setEditing(false);
            setActionError(null);
            void refresh();
          }}
        />
      </ScrollView>
    );
  }

  return (
    <ScrollView style={styles.container}>
      <Card style={styles.card}>
        <Text style={styles.name}>{user.profile.full_name || 'No name provided'}</Text>
        <Text style={styles.email}>{user.email}</Text>
        <Text style={styles.meta}>
          {user.is_suspended ? 'Suspended' : 'Active'} · Member since{' '}
          {new Date(user.date_joined).toLocaleDateString()}
        </Text>
      </Card>

      <Card style={styles.card}>
        <Text style={styles.sectionTitle}>Activity</Text>
        <Row label="Listings" value={user.product_count} />
        <Row label="Orders (as buyer)" value={user.order_count} />
        <Row label="Items sold" value={user.sold_count} />
        <Row label="Wallet balance" value={`TZS ${Number(user.wallet_balance).toLocaleString()}`} />
      </Card>

      {actionError ? <Text style={styles.error}>{actionError}</Text> : null}

      <Button
        title={user.is_suspended ? 'Reactivate account' : 'Suspend account'}
        variant={user.is_suspended ? 'primary' : 'danger'}
        disabled={busy || user.is_staff}
        onPress={() => void toggleSuspension()}
      />
      {user.is_staff ? (
        <Text style={styles.hint}>Administrator accounts cannot be suspended.</Text>
      ) : null}

      <Button
        title="Edit account"
        variant="secondary"
        disabled={busy || user.is_staff}
        onPress={() => {
          setEditing(true);
          setActionError(null);
        }}
      />
      {user.is_staff ? (
        <Text style={styles.hint}>Administrator accounts cannot be edited.</Text>
      ) : null}

      {!user.is_staff ? (
        <Button
          title={confirmDelete ? 'Tap again to confirm delete' : 'Delete account'}
          variant="danger"
          loading={busy}
          onPress={() => void handleDelete()}
        />
      ) : null}

      <Button title="Back to users" variant="secondary" onPress={() => navigation.goBack()} />
    </ScrollView>
  );
}

function Row({ label, value }: { label: string; value: string | number }) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={styles.rowValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    padding: spacing.lg,
    gap: spacing.lg,
  },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background,
    gap: spacing.lg,
    padding: spacing.lg,
  },
  error: {
    ...typography.body,
    color: colors.error,
    textAlign: 'center',
  },
  card: {
    gap: spacing.sm,
  },
  name: {
    ...typography.title,
    fontSize: 20,
  },
  email: {
    ...typography.body,
    color: colors.textSecondary,
  },
  meta: {
    ...typography.label,
  },
  sectionTitle: {
    ...typography.subtitle,
    fontWeight: '700',
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  rowLabel: {
    ...typography.body,
    color: colors.textSecondary,
  },
  rowValue: {
    ...typography.body,
    fontWeight: '600',
  },
  hint: {
    ...typography.label,
    color: colors.textSecondary,
    textAlign: 'center',
  },
  fieldLabel: {
    ...typography.body,
    fontWeight: '600',
    marginTop: spacing.sm,
  },
  roleRow: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  rolePill: {
    flex: 1,
    paddingVertical: spacing.sm,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: 'center',
    backgroundColor: colors.surface,
  },
  rolePillActive: {
    borderColor: colors.primary,
    backgroundColor: colors.primary,
  },
  roleText: {
    ...typography.body,
    color: colors.textSecondary,
  },
  roleTextActive: {
    color: colors.onPrimary,
    fontWeight: '600',
  },
});
