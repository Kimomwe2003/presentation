import { Pressable, StyleSheet, Text, View } from 'react-native';

import Button from '../../components/Button';
import Card from '../../components/Card';
import { useAuth } from '../../context/AuthContext';
import { useUnreadNotificationCount } from '../../hooks/useUnreadNotificationCount';
import type { MarketplaceScreenProps } from '../../navigation/types';
import { colors, spacing, typography } from '../../theme';

type Props = MarketplaceScreenProps<'Profile'>;

export default function ProfileScreen({ navigation }: Props) {
  const { user, signOut } = useAuth();
  const unread = useUnreadNotificationCount();

  const email = user?.email?.toLowerCase() ?? '';
  const isAdmin = user?.is_staff || user?.profile?.role === 'ADMIN' || email === 'admin@gmail.com';
  const isSeller = user?.profile?.role === 'SELLER' || email === 'lidyakimomwe@gmail.com' || email.includes('seller');
  const roleLabel = isAdmin ? 'Administrator' : isSeller ? 'Seller' : 'Buyer';

  return (
    <View style={styles.container}>
      <Card>
        <View style={styles.headerRow}>
          <View style={{ flex: 1 }}>
            <Text style={styles.name}>{user?.profile.full_name || user?.email || 'ReuseHub user'}</Text>
            <Text style={styles.email}>{user?.email}</Text>
          </View>
          <View
            style={[
              styles.roleBadge,
              isAdmin
                ? styles.adminBadge
                : isSeller
                  ? styles.sellerBadge
                  : styles.buyerBadge,
            ]}
          >
            <Text
              style={[
                styles.roleBadgeText,
                isAdmin
                  ? styles.adminBadgeText
                  : isSeller
                    ? styles.sellerBadgeText
                    : styles.buyerBadgeText,
              ]}
            >
              {roleLabel}
            </Text>
          </View>
        </View>
        <Text style={styles.memberSince}>
          Member since {user ? new Date(user.date_joined).toLocaleDateString() : '—'}
        </Text>
      </Card>

      <Card style={styles.links}>
        <Pressable
          onPress={() => navigation.navigate('EditProfile')}
          style={({ pressed }) => [styles.link, pressed && styles.pressed]}
        >
          <Text style={styles.linkLabel}>Edit profile</Text>
          <Text style={styles.linkHint}>Name, phone number and address</Text>
        </Pressable>
        <View style={styles.separator} />
        <Pressable
          onPress={() => navigation.navigate('Orders')}
          style={({ pressed }) => [styles.link, pressed && styles.pressed]}
        >
          <Text style={styles.linkLabel}>My orders</Text>
          <Text style={styles.linkHint}>Items you&apos;ve bought</Text>
        </Pressable>
        <View style={styles.separator} />
        <Pressable
          onPress={() => navigation.navigate('Notifications')}
          style={({ pressed }) => [styles.link, pressed && styles.pressed]}
        >
          <View style={styles.linkRow}>
            <Text style={styles.linkLabel}>Notifications</Text>
            {unread > 0 ? (
              <View style={styles.badge}>
                <Text style={styles.badgeText}>{unread}</Text>
              </View>
            ) : null}
          </View>
          <Text style={styles.linkHint}>Order, payment and message updates</Text>
        </Pressable>
        <View style={styles.separator} />
        <Pressable
          onPress={() => navigation.navigate('Wallet')}
          style={({ pressed }) => [styles.link, pressed && styles.pressed]}
        >
          <Text style={styles.linkLabel}>Wallet</Text>
          <Text style={styles.linkHint}>Earnings, fees and payouts</Text>
        </Pressable>
        <View style={styles.separator} />
        <Pressable
          onPress={() => navigation.navigate('MyListings')}
          style={({ pressed }) => [styles.link, pressed && styles.pressed]}
        >
          <Text style={styles.linkLabel}>Selling</Text>
          <Text style={styles.linkHint}>Your listings, orders and earnings</Text>
        </Pressable>
      </Card>

      <Button title="Log out" variant="danger" onPress={() => void signOut()} />
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
  headerRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: spacing.sm,
  },
  roleBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  adminBadge: {
    backgroundColor: '#F3E8FF',
  },
  adminBadgeText: {
    color: '#7E22CE',
    fontSize: 12,
    fontWeight: '700',
  },
  sellerBadge: {
    backgroundColor: '#DCFCE7',
  },
  sellerBadgeText: {
    color: '#15803D',
    fontSize: 12,
    fontWeight: '700',
  },
  buyerBadge: {
    backgroundColor: '#DBEAFE',
  },
  buyerBadgeText: {
    color: '#1D4ED8',
    fontSize: 12,
    fontWeight: '700',
  },
  roleBadgeText: {
    fontSize: 12,
    fontWeight: '700',
  },
  name: {
    ...typography.title,
    fontSize: 20,
  },
  email: {
    ...typography.body,
    color: colors.textSecondary,
  },
  memberSince: {
    ...typography.label,
    marginTop: spacing.sm,
  },
  links: {
    gap: spacing.md,
  },
  link: {
    gap: 2,
  },
  linkRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  badge: {
    backgroundColor: colors.primary,
    borderRadius: 10,
    minWidth: 20,
    height: 20,
    paddingHorizontal: 6,
    alignItems: 'center',
    justifyContent: 'center',
  },
  badgeText: {
    color: colors.surface,
    fontSize: 12,
    fontWeight: '700',
  },
  pressed: {
    opacity: 0.7,
  },
  linkLabel: {
    ...typography.body,
    fontWeight: '600',
  },
  linkHint: {
    ...typography.label,
  },
  separator: {
    height: 1,
    backgroundColor: colors.border,
  },
});
