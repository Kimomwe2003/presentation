/**
 * Typed wrappers around the Prompt 16 adminpanel API.
 *
 * Every endpoint requires a staff/superuser session; the backend enforces this
 * (401 for anonymous, 403 for non-staff). The admin UI is hidden from regular
 * members, but the client still surfaces the server's "Administrator
 * privileges are required." error if a non-staff user ever calls through.
 */
import { client } from './client';
import type {
  AdminDashboard,
  AdminProduct,
  AdminProductRemoval,
  AdminReportSummary,
  AdminUser,
  AdminUserAction,
  AdminUserDetail,
  AdminUserUpdatePayload,
  AuditLogEntry,
  Category,
  Paginated,
  WithdrawalRequest,
} from './types';

/** GET /api/admin/dashboard/ — aggregated platform stats + recent activity. */
export async function fetchAdminDashboard(): Promise<AdminDashboard> {
  const { data } = await client.get<AdminDashboard>('/admin/dashboard/');
  return data;
}

/** GET /api/admin/users/ — paginated, search by email/username/full name. */
export async function fetchAdminUsers(
  params: { search?: string; page?: number } = {},
): Promise<Paginated<AdminUser>> {
  const { data } = await client.get<Paginated<AdminUser>>('/admin/users/', { params });
  return data;
}

/** GET /api/admin/users/{id}/ — user detail incl. activity + wallet balance. */
export async function fetchAdminUserDetail(userId: number): Promise<AdminUserDetail> {
  const { data } = await client.get<AdminUserDetail>(`/admin/users/${userId}/`);
  return data;
}

/** POST /api/admin/users/{id}/suspend/ — suspend a member account. */
export async function suspendUser(userId: number): Promise<AdminUserAction> {
  const { data } = await client.post<AdminUserAction>(`/admin/users/${userId}/suspend/`);
  return data;
}

/** POST /api/admin/users/{id}/activate/ — reactivate a suspended account. */
export async function activateUser(userId: number): Promise<AdminUserAction> {
  const { data } = await client.post<AdminUserAction>(`/admin/users/${userId}/activate/`);
  return data;
}

/** PATCH /api/admin/users/{id}/ — edit a member account (profile + email). */
export async function updateUser(
  userId: number,
  payload: Partial<AdminUserUpdatePayload>,
): Promise<AdminUserDetail> {
  const { data } = await client.patch<AdminUserDetail>(`/admin/users/${userId}/`, payload);
  return data;
}

/** DELETE /api/admin/users/{id}/ — permanently remove a member account. */
export async function deleteUser(userId: number): Promise<void> {
  await client.delete(`/admin/users/${userId}/`);
}

/** GET /api/admin/products/ — all products (active + inactive), searchable. */
export async function fetchAdminProducts(
  params: { search?: string; page?: number } = {},
): Promise<Paginated<AdminProduct>> {
  const { data } = await client.get<Paginated<AdminProduct>>('/admin/products/', { params });
  return data;
}

/** POST /api/admin/products/{id}/remove/ — deactivate with a required reason. */
export async function removeProduct(
  productId: number,
  reason: string,
): Promise<AdminProductRemoval> {
  const { data } = await client.post<AdminProductRemoval>(`/admin/products/${productId}/remove/`, {
    reason,
  });
  return data;
}

/** POST /api/admin/categories/ — create a category (slug auto-generated). */
export async function createCategory(payload: { name: string }): Promise<Category> {
  const { data } = await client.post<Category>('/admin/categories/', payload);
  return data;
}

/** PATCH /api/admin/categories/{id}/ — rename / move / deactivate. */
export async function updateCategory(
  categoryId: number,
  payload: Partial<Pick<Category, 'name' | 'slug' | 'parent' | 'is_active'>>,
): Promise<Category> {
  const { data } = await client.patch<Category>(`/admin/categories/${categoryId}/`, payload);
  return data;
}

// ---------------------------------------------------------------------------
// Audit log (Prompt 17)
// ---------------------------------------------------------------------------

/** GET /api/audit-logs/ — paginated, filter by actor/action/target/date. */
export async function fetchAuditLogs(
  params: {
    page?: number;
    actor?: number;
    action?: string;
    target_model?: string;
    created_after?: string;
    created_before?: string;
  } = {},
): Promise<Paginated<AuditLogEntry>> {
  const { data } = await client.get<Paginated<AuditLogEntry>>('/audit-logs/', { params });
  return data;
}

/** GET /api/audit-logs/{id}/ — single audit entry. */
export async function fetchAuditLogEntry(entryId: number): Promise<AuditLogEntry> {
  const { data } = await client.get<AuditLogEntry>(`/audit-logs/${entryId}/`);
  return data;
}

// ---------------------------------------------------------------------------
// Reports (Prompt 17)
// ---------------------------------------------------------------------------

/** GET /api/admin/reports/summary/ — transaction volume, fees, new users. */
export async function fetchAdminReports(days = 30): Promise<AdminReportSummary> {
  const { data } = await client.get<AdminReportSummary>('/admin/reports/summary/', {
    params: { days },
  });
  return data;
}

// ---------------------------------------------------------------------------
// Withdrawals Management
// ---------------------------------------------------------------------------

/** GET /api/withdrawals/admin/pending/ — get processing queue. */
export async function fetchAdminPendingWithdrawals(): Promise<WithdrawalRequest[]> {
  const { data } = await client.get<WithdrawalRequest[]>('/withdrawals/admin/pending/');
  return data;
}

/** POST /api/withdrawals/{id}/process/ — transition PENDING -> PROCESSING. */
export async function processAdminWithdrawal(
  id: number,
  admin_notes?: string,
): Promise<WithdrawalRequest> {
  const { data } = await client.post<WithdrawalRequest>(`/withdrawals/${id}/process/`, {
    admin_notes,
  });
  return data;
}

/** POST /api/withdrawals/{id}/complete/ — transition PROCESSING -> COMPLETED. */
export async function completeAdminWithdrawal(
  id: number,
  admin_notes?: string,
): Promise<WithdrawalRequest> {
  const { data } = await client.post<WithdrawalRequest>(`/withdrawals/${id}/complete/`, {
    admin_notes,
  });
  return data;
}

/** POST /api/withdrawals/{id}/reject/ — transition to REJECTED (triggers refund). */
export async function rejectAdminWithdrawal(
  id: number,
  admin_notes?: string,
): Promise<WithdrawalRequest> {
  const { data } = await client.post<WithdrawalRequest>(`/withdrawals/${id}/reject/`, {
    admin_notes,
  });
  return data;
}

