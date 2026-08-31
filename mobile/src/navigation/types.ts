import type { NavigatorScreenParams, CompositeScreenProps } from '@react-navigation/native';
import type { BottomTabScreenProps } from '@react-navigation/bottom-tabs';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import type { ProductFilters } from '../api/types';

export type AuthStackParamList = {
  Login: undefined;
  Register: undefined;
  ForgotPassword: undefined;
  ResetPassword: { email: string; devCode?: string };
};

export type AppTabParamList = {
  Home: undefined;
  Search: { filters?: ProductFilters } | undefined;
  Selling: undefined;
  Chat: undefined;
  Profile: undefined;
  Admin: undefined;
};

export type RootStackParamList = {
  Tabs: NavigatorScreenParams<AppTabParamList> | undefined;
  Auth: NavigatorScreenParams<AuthStackParamList> | undefined;
  ProductDetails: { productId: number; productName?: string };
  Category: { categoryId: number; categoryName: string };
  Filters: { current: ProductFilters } | undefined;
  Orders: undefined;
  Selling: undefined;
  OrderDetails: { orderId: number; sellerView?: boolean };
  Payment: { orderId: number };
  Wallet: undefined;
  MyListings: undefined;
  AddProduct: undefined;
  EditProduct: { productId: number };
  Earnings: undefined;
  Conversation: { conversationId: number };
  Notifications: undefined;
  Review: { orderItemId: number; productName?: string };
  AdminUsers: undefined;
  AdminUserDetail: { userId: number; email?: string };
  AdminProducts: undefined;
  AuditLog: undefined;
  Reports: undefined;
  AdminWithdrawals: undefined;
  Cart: undefined;
  Checkout: undefined;
  Withdraw: undefined;
  EditProfile: undefined;
  QRCode: { orderId: number };
  ScanQR: undefined;
};

/** A screen rendered inside the tab navigator that may navigate to root screens. */
export type MarketplaceScreenProps<T extends keyof AppTabParamList> = CompositeScreenProps<
  BottomTabScreenProps<AppTabParamList, T>,
  NativeStackScreenProps<RootStackParamList>
>;
