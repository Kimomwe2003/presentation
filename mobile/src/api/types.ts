/**
 * Shared types for the backend API (Prompt 02 auth endpoints + Prompt 04 catalog).
 */

/** POST /api/auth/register/ and /api/auth/login/ response. */
export interface AuthResponse {
  access: string;
  refresh: string;
}

/** POST /api/auth/refresh/ response (rotation enabled on the backend). */
export interface RefreshResponse {
  access: string;
  refresh?: string;
}

export interface RegisterPayload {
  email: string;
  password: string;
  password_confirmation: string;
  full_name: string;
  phone_number?: string;
  role?: 'BUYER' | 'SELLER';
}

export interface LoginPayload {
  email: string;
  password: string;
}

/** POST /api/auth/password/forgot/ response. */
export interface ForgotPasswordResponse {
  detail: string;
  /** Only present from the backend in DEBUG builds (no SMTP configured). */
  debug_code?: string;
}

export interface ResetPasswordPayload {
  email: string;
  code: string;
  new_password: string;
  new_password_confirmation: string;
}

export interface UserProfile {
  full_name: string;
  profile_picture: string | null;
  address: string | null;
  phone_number: string | null;
  role: 'BUYER' | 'SELLER' | 'ADMIN';
  account_status: 'ACTIVE' | 'SUSPENDED';
  created_at: string;
  updated_at: string;
}

/** GET /api/users/me/ response. */
export interface User {
  id: number;
  email: string;
  date_joined: string;
  is_staff: boolean;
  profile: UserProfile;
}

/**
 * DRF error envelope. Field validation errors map field -> messages; a
 * non-field error arrives as `detail`. `non_field_errors` is used by some
 * serializers.
 */
export interface ApiErrorBody {
  detail?: string;
  non_field_errors?: string[];
  [field: string]: string[] | string | undefined;
}

// ---------------------------------------------------------------------------
// Catalog (Prompt 04 API)
// ---------------------------------------------------------------------------

export interface Category {
  id: number;
  name: string;
  slug: string;
  parent: number | null;
  is_active: boolean;
}

/** Public seller summary — deliberately excludes contact details (Prompt 13). */
export interface Seller {
  id: number;
  email: string;
  full_name: string;
  profile_picture: string | null;
  average_rating: number | null;
  rating_count: number;
}

export interface ProductImage {
  id: number;
  image: string;
  is_primary: boolean;
  order: number;
}

export type ProductCondition = 'NEW' | 'LIKE_NEW' | 'GOOD' | 'FAIR' | 'USED';

export type ProductStatus = 'DRAFT' | 'ACTIVE' | 'INACTIVE' | 'SOLD';

export interface ProductSummary {
  id: number;
  name: string;
  price: string;
  condition: ProductCondition;
  status: ProductStatus;
  location: string;
  category: Category;
  seller: Seller;
  primary_image: string | null;
  average_rating: number | null;
  rating_count: number;
  created_at: string;
}

export interface ProductDetail extends ProductSummary {
  description: string;
  quantity: number;
  images: ProductImage[];
  updated_at: string;
}

export interface Favorite {
  id: number;
  product: ProductSummary;
  created_at: string;
}

/** DRF PageNumberPagination envelope. */
export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

/** User-facing product filters (mirror of the backend ProductFilter). */
export interface ProductFilters {
  category?: number;
  condition?: ProductCondition;
  minPrice?: number;
  maxPrice?: number;
  location?: string;
  /** Owner-only filter used by the seller dashboard (all statuses). */
  seller?: number;
}

// ---------------------------------------------------------------------------
// Orders (Prompt 08 API)
// ---------------------------------------------------------------------------

export type OrderStatus =
  | 'pending_payment'
  | 'paid'
  | 'confirmed'
  | 'shipped'
  | 'delivered'
  | 'completed'
  | 'cancelled'
  | 'payment_failed'
  | 'refunded';

export type OrderItemStatus =
  'pending' | 'confirmed' | 'shipped' | 'delivered' | 'completed' | 'cancelled';

export interface OrderAction {
  action: string;
  label: string;
}

export interface OrderSeller {
  id: number;
  full_name: string;
}

export interface OrderBuyer {
  id: number;
  email: string;
  full_name: string;
  phone_number: string | null;
}

export interface OrderItem {
  id: number;
  product_id: number;
  product_name: string;
  product_sku: string;
  quantity: number;
  unit_price: string;
  attributes: Record<string, unknown>;
  item_status: OrderItemStatus;
  item_status_label: string;
  seller: OrderSeller | null;
  line_total: string;
  available_actions: OrderAction[];
}

export interface Order {
  id: number;
  order_number: string;
  status: OrderStatus;
  status_label: string;
  payment_method: string;
  shipping_address: Record<string, unknown>;
  subtotal: string;
  shipping_cost: string;
  total: string;
  total_pretty: string;
  placed_at: string;
  buyer: OrderBuyer | null;
  items: OrderItem[];
  available_actions: OrderAction[];
}

// ---------------------------------------------------------------------------
// Payments (Prompt 09 — ClickPesa)
// ---------------------------------------------------------------------------

export type PaymentStatus = 'pending' | 'successful' | 'failed' | 'expired';

export interface Payment {
  id: number;
  order: number;
  amount: string;
  provider: string;
  provider_label: string;
  status: PaymentStatus;
  status_label: string;
  network_channel: string;
  created_at: string;
  failure_reason?: string;
}

/** Response shared by initiate/status/verify endpoints. */
export interface PaymentState {
  payment: Payment | null;
  order: {
    id: number;
    status: OrderStatus;
    status_label: string;
  };
}

// ---------------------------------------------------------------------------
// Wallet & ledger (Prompt 10)
// ---------------------------------------------------------------------------

export type LedgerType =
  'credit' | 'debit' | 'platform_fee' | 'withdrawal' | 'refund' | 'payment' | 'adjustment';

export type LedgerStatus = 'pending' | 'completed' | 'failed' | 'cancelled';

/** GET /api/wallet/balance/ */
export interface WalletBalance {
  balance: string;
  total_earnings: string;
  total_withdrawn: string;
}

/** GET /api/wallet/pending-earnings/ — projected net of sold-but-uncompleted items. */
export interface PendingEarnings {
  pending_earnings: string;
}

/** A row from GET /api/wallet/transactions/ (amount is signed). */
export interface LedgerTransaction {
  id: number;
  type: LedgerType;
  type_label: string;
  amount: string;
  status: LedgerStatus;
  status_label: string;
  reference: string;
  description: string;
  order_item_id: number | null;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Chat (Prompt 13)
// ---------------------------------------------------------------------------

/** A participant as seen by a conversation's counterpart field. */
export interface ChatParticipant {
  id: number;
  email: string;
  full_name: string;
  profile_picture: string | null;
}

/** Lightweight preview of the most recent message in a conversation. */
export interface ChatMessagePreview {
  id: number;
  sender: number;
  body: string;
  is_read: boolean;
  created_at: string;
}

/** GET /api/chats/ item. */
export interface Conversation {
  id: number;
  counterpart: ChatParticipant | null;
  product_id: number | null;
  last_message: ChatMessagePreview | null;
  unread_count: number;
  created_at: string;
  updated_at: string;
}

/** One message within a conversation (GET/POST /api/chats/{id}/messages/). */
export interface ChatMessage {
  id: number;
  conversation: number;
  sender: number;
  sender_detail: ChatParticipant;
  body: string;
  is_read: boolean;
  created_at: string;
}

/** Paginated message history envelope (newest-first, load-more on scroll). */
export type NotificationType =
  'order_update' | 'payment_result' | 'new_message' | 'withdrawal_update' | 'system';

export interface AppNotification {
  id: number;
  type: NotificationType;
  type_label: string;
  title: string;
  body: string;
  is_read: boolean;
  related_type: string | null;
  related_id: number | null;
  created_at: string;
}

export interface UnreadCount {
  unread_count: number;
}

export interface MessagePage {
  results: ChatMessage[];
  next: string | null;
  count: number;
}

// ---------------------------------------------------------------------------
// Reviews & ratings (Prompt 15)
// ---------------------------------------------------------------------------

export interface Review {
  id: number;
  order_item: number;
  buyer: { id: number; full_name: string };
  product: number;
  product_name: string;
  rating: number;
  comment: string;
  created_at: string;
}

/** Payload for POST /api/reviews/ */
export interface ReviewPayload {
  order_item_id: number;
  rating: number;
  comment?: string;
}

/** Seller public profile from GET /api/reviews/seller/{id}/ */
export interface SellerProfile {
  seller: Seller;
  average_rating: number | null;
  rating_count: number;
  reviews: Paginated<Review>;
}

// ---------------------------------------------------------------------------
// Admin dashboard & moderation (Prompt 16 — staff only)
// ---------------------------------------------------------------------------

export type AccountStatus = 'ACTIVE' | 'SUSPENDED';

export interface AdminUserProfile {
  full_name: string;
  profile_picture: string | null;
  phone_number: string | null;
  address: string | null;
  account_status: AccountStatus;
  created_at: string;
}

/** Role choices used by the admin edit form. */
export type AdminRole = 'BUYER' | 'SELLER' | 'ADMIN';

/** PATCH body for /api/admin/users/{id}/ — editable admin-user fields. */
export interface AdminUserUpdatePayload {
  email: string;
  full_name: string;
  phone_number: string | null;
  address: string;
  role: AdminRole;
}

/** A user as shown in the admin list/detail (GET /api/admin/users/...). */
export interface AdminUser {
  id: number;
  email: string;
  username: string;
  is_staff: boolean;
  is_superuser: boolean;
  is_active: boolean;
  date_joined: string;
  is_suspended: boolean;
  profile: AdminUserProfile;
}

/** User detail extended with aggregated activity (GET /api/admin/users/{id}/). */
export interface AdminUserDetail extends AdminUser {
  product_count: number;
  order_count: number;
  sold_count: number;
  wallet_balance: string;
}

/** A product as shown in the admin moderation list. */
export interface AdminProduct {
  id: number;
  name: string;
  price: string;
  condition: ProductCondition;
  quantity: number;
  status: ProductStatus;
  location: string;
  seller: { id: number; email: string; full_name: string };
  category: number;
  category_name: string | null;
  image_url: string | null;
  review_count: number;
  average_rating: number | null;
  created_at: string;
  updated_at: string;
}

/** One recent cross-app event in the dashboard feed. */
export interface AdminActivity {
  type: 'order' | 'review' | 'withdrawal';
  message: string;
  created_at: string;
}

/** GET /api/admin/dashboard/ aggregated stats. */
export interface AdminDashboard {
  users: { total: number; active: number; suspended: number };
  products: { total: number; active: number };
  orders_by_status: Record<string, number>;
  order_total: number;
  transaction_value: string;
  platform_fees_collected: string;
  withdrawals: { pending: number; processing: number; completed: number };
  failed_payments: number;
  recent_activity: AdminActivity[];
}

/** Response from user suspend/activate endpoints. */
export interface AdminUserAction {
  id: number;
  suspended: boolean;
}

/** Response from POST /api/admin/products/{id}/remove/. */
export interface AdminProductRemoval {
  id: number;
  status: ProductStatus;
  reason: string;
  removed: boolean;
}

// ---------------------------------------------------------------------------
// Audit log & reporting (Prompt 17 — staff only)
// ---------------------------------------------------------------------------

/** One append-only audit entry (GET /api/audit-logs/). */
export interface AuditLogEntry {
  id: number;
  actor_id: number | null;
  actor_email: string | null;
  action: string;
  action_label: string;
  target_model: string;
  target_id: number | null;
  description: string;
  ip_address: string | null;
  before_data: Record<string, unknown> | null;
  after_data: Record<string, unknown> | null;
  created_at: string;
}

/** GET /api/admin/reports/summary/ — time-series reporting figures. */
export interface AdminReportSummary {
  days: number;
  transaction_volume: { date: string; total: string }[];
  fee_revenue: { date: string; total: string }[];
  new_users: { date: string; count: number }[];
}

// ---------------------------------------------------------------------------
// Cart (Prompt 07 API)
// ---------------------------------------------------------------------------

/** One row of GET /api/cart/items/. */
export interface CartItem {
  id: number;
  product_id: number;
  product_name: string;
  product_image: string | null;
  condition: ProductCondition;
  quantity: number;
  attributes: Record<string, unknown>;
  price: string;
  total: string;
  created_at: string;
}

/** GET /api/cart/ response. */
export interface Cart {
  id: number;
  items: CartItem[];
  item_count: number;
  subtotal: string;
  subtotal_pretty: string;
  created_at: string;
}

/** Payload for POST /api/cart/items/ (add to cart). */
export interface CartItemPayload {
  product_id: number;
  quantity?: number;
  attributes?: Record<string, unknown>;
}

/** Payload for POST /api/orders/ (checkout the current cart). */
export interface CheckoutPayload {
  payment_method: string;
  shipping_address?: Record<string, unknown>;
  shipping_cost?: string;
}

// ---------------------------------------------------------------------------
// Withdrawals (Prompt 12)
// ---------------------------------------------------------------------------

export type WithdrawalProvider = 'mpesa' | 'tigo_pesa' | 'airtel_money' | 'halopesa';

export type WithdrawalStatus = 'pending' | 'processing' | 'completed' | 'rejected' | 'failed';

export interface WithdrawalRequest {
  id: number;
  amount: string;
  provider: WithdrawalProvider;
  provider_label: string;
  mobile_money_number: string;
  status: WithdrawalStatus;
  status_label: string;
  reference: string;
  admin_notes: string;
  created_at: string;
  processed_at: string | null;
}

export interface WithdrawalPayload {
  amount: string;
  provider: WithdrawalProvider;
  mobile_money_number: string;
}
