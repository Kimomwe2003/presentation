import { createNativeStackNavigator } from '@react-navigation/native-stack';

import { useAuth } from '../context/AuthContext';
import SplashScreen from '../screens/auth/SplashScreen';
import CategoryScreen from '../screens/marketplace/CategoryScreen';
import FiltersScreen from '../screens/marketplace/FiltersScreen';
import ProductDetailsScreen from '../screens/marketplace/ProductDetailsScreen';
import OrderDetailsScreen from '../screens/orders/OrderDetailsScreen';
import OrdersScreen from '../screens/orders/OrdersScreen';
import PaymentScreen from '../screens/payment/PaymentScreen';
import SellerOrdersScreen from '../screens/orders/SellerOrdersScreen';
import AddProductScreen from '../screens/selling/AddProductScreen';
import EarningsScreen from '../screens/selling/EarningsScreen';
import EditProductScreen from '../screens/selling/EditProductScreen';
import MyListingsScreen from '../screens/selling/MyListingsScreen';
import BalanceScreen from '../screens/wallet/BalanceScreen';
import ConversationScreen from '../screens/chat/ConversationScreen';
import NotificationsScreen from '../screens/notifications/NotificationsScreen';
import ReviewScreen from '../screens/reviews/ReviewScreen';
import AdminUsersScreen from '../screens/admin/AdminUsersScreen';
import AdminUserDetailScreen from '../screens/admin/AdminUserDetailScreen';
import AdminProductsScreen from '../screens/admin/AdminProductsScreen';
import AuditLogScreen from '../screens/admin/AuditLogScreen';
import ReportsScreen from '../screens/admin/ReportsScreen';
import AdminWithdrawalsScreen from '../screens/admin/AdminWithdrawalsScreen';
import CartScreen from '../screens/cart/CartScreen';
import CheckoutScreen from '../screens/cart/CheckoutScreen';
import WithdrawalScreen from '../screens/wallet/WithdrawalScreen';
import EditProfileScreen from '../screens/profile/EditProfileScreen';
import { colors } from '../theme';
import AppStack from './AppStack';
import AuthStack from './AuthStack';
import type { RootStackParamList } from './types';

const Stack = createNativeStackNavigator<RootStackParamList>();

/**
 * Session-driven root. While the stored token is being validated the Splash
 * screen renders; afterwards the user is either in the Auth stack (logged out)
 * or the App stack (logged in). Marketplace screens that need a chrome (a real
 * header / modal presentation) live at this level, above the tabs.
 */
export default function RootNavigator() {
  const { status } = useAuth();

  if (status === 'loading') {
    return <SplashScreen />;
  }

  return (
    <Stack.Navigator
      id={undefined}
      screenOptions={{
        headerShown: false,
        headerShadowVisible: false,
        headerStyle: { backgroundColor: colors.background },
        headerTintColor: colors.text,
        contentStyle: { backgroundColor: colors.background },
      }}
    >
      {status === 'authenticated' ? (
        <>
          <Stack.Screen name="Tabs" component={AppStack} />
          <Stack.Screen
            name="ProductDetails"
            component={ProductDetailsScreen}
            options={({ route }) => ({
              headerShown: true,
              title: route.params.productName ?? 'Details',
            })}
          />
          <Stack.Screen
            name="Category"
            component={CategoryScreen}
            options={({ route }) => ({
              headerShown: true,
              title: route.params.categoryName,
            })}
          />
          <Stack.Screen
            name="Filters"
            component={FiltersScreen}
            options={{ headerShown: true, title: 'Filters', presentation: 'modal' }}
          />
          <Stack.Screen
            name="Orders"
            component={OrdersScreen}
            options={{ headerShown: true, title: 'My orders' }}
          />
          <Stack.Screen
            name="Selling"
            component={SellerOrdersScreen}
            options={{ headerShown: true, title: 'Selling' }}
          />
          <Stack.Screen
            name="OrderDetails"
            component={OrderDetailsScreen}
            options={({ route }) => ({
              headerShown: true,
              title: route.params.sellerView ? 'Order details' : 'Order details',
            })}
          />
          <Stack.Screen
            name="Payment"
            component={PaymentScreen}
            options={{ headerShown: true, title: 'Payment' }}
          />
          <Stack.Screen
            name="Wallet"
            component={BalanceScreen}
            options={{ headerShown: true, title: 'My wallet' }}
          />
          <Stack.Screen
            name="MyListings"
            component={MyListingsScreen}
            options={{ headerShown: true, title: 'My listings' }}
          />
          <Stack.Screen
            name="AddProduct"
            component={AddProductScreen}
            options={{ headerShown: true, title: 'Add listing' }}
          />
          <Stack.Screen
            name="EditProduct"
            component={EditProductScreen}
            options={{ headerShown: true, title: 'Edit listing' }}
          />
          <Stack.Screen
            name="Earnings"
            component={EarningsScreen}
            options={{ headerShown: true, title: 'Earnings' }}
          />
          <Stack.Screen
            name="Conversation"
            component={ConversationScreen}
            options={{ headerShown: true, title: 'Messages' }}
          />
          <Stack.Screen
            name="Notifications"
            component={NotificationsScreen}
            options={{ headerShown: true, title: 'Notifications' }}
          />
          <Stack.Screen
            name="Review"
            component={ReviewScreen}
            options={{ headerShown: true, title: 'Write a review' }}
          />
          <Stack.Screen
            name="Cart"
            component={CartScreen}
            options={{ headerShown: true, title: 'My cart' }}
          />
          <Stack.Screen
            name="Checkout"
            component={CheckoutScreen}
            options={{ headerShown: true, title: 'Checkout' }}
          />
          <Stack.Screen
            name="Withdraw"
            component={WithdrawalScreen}
            options={{ headerShown: true, title: 'Withdraw' }}
          />
          <Stack.Screen
            name="AdminUsers"
            component={AdminUsersScreen}
            options={{ headerShown: true, title: 'Manage users' }}
          />
          <Stack.Screen
            name="AdminUserDetail"
            component={AdminUserDetailScreen}
            options={{ headerShown: true, title: 'User details' }}
          />
          <Stack.Screen
            name="AdminProducts"
            component={AdminProductsScreen}
            options={{ headerShown: true, title: 'Moderate products' }}
          />
          <Stack.Screen
            name="AuditLog"
            component={AuditLogScreen}
            options={{ headerShown: true, title: 'Audit log' }}
          />
          <Stack.Screen
            name="Reports"
            component={ReportsScreen}
            options={{ headerShown: true, title: 'Reports' }}
          />
          <Stack.Screen
            name="AdminWithdrawals"
            component={AdminWithdrawalsScreen}
            options={{ headerShown: true, title: 'Withdrawal Approvals' }}
          />
          <Stack.Screen
            name="EditProfile"
            component={EditProfileScreen}
            options={{ headerShown: true, title: 'Edit profile' }}
          />
        </>
      ) : (
        <Stack.Screen name="Auth" component={AuthStack} />
      )}
    </Stack.Navigator>
  );
}
