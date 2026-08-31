/**
 * Typed wrappers around the Prompt 04 catalog API.
 *
 * All favorites calls require an authenticated session (the client interceptor
 * attaches the access token). Listing/category calls are public.
 */
import { client } from './client';
import type {
  Category,
  Favorite,
  Paginated,
  ProductCondition,
  ProductDetail,
  ProductFilters,
  ProductImage,
  ProductStatus,
  ProductSummary,
} from './types';

function buildParams(filters: ProductFilters, extra?: { search?: string; ordering?: string }) {
  const params: Record<string, string> = {};
  if (extra?.search) params.search = extra.search;
  if (extra?.ordering) params.ordering = extra.ordering;
  if (filters.category) params.category = String(filters.category);
  if (filters.condition) params.condition = filters.condition;
  if (filters.minPrice != null) params.min_price = String(filters.minPrice);
  if (filters.maxPrice != null) params.max_price = String(filters.maxPrice);
  if (filters.location?.trim()) params.location = filters.location.trim();
  if (filters.seller) params.seller = String(filters.seller);
  return params;
}

export async function fetchProducts(
  filters: ProductFilters,
  extra?: { search?: string; ordering?: string },
): Promise<Paginated<ProductSummary>> {
  const { data } = await client.get<Paginated<ProductSummary>>('/products/', {
    params: buildParams(filters, extra),
  });
  return data;
}

/** Fetch an absolute pagination URL returned as `next` by the API. */
export async function fetchProductsPage(url: string): Promise<Paginated<ProductSummary>> {
  const { data } = await client.get<Paginated<ProductSummary>>(url);
  return data;
}

export async function fetchProduct(id: number): Promise<ProductDetail> {
  const { data } = await client.get<ProductDetail>(`/products/${id}/`);
  return data;
}

// ---------------------------------------------------------------------------
// Seller dashboard (Prompt 11) — create/update/delete + image management.
// ---------------------------------------------------------------------------

export interface ProductWritePayload {
  name: string;
  description?: string;
  price: string;
  condition: ProductCondition;
  quantity?: number;
  location?: string;
  category?: number | null;
  status?: ProductStatus;
}

/** Shape returned by create/update (ProductWriteSerializer — no images/seller). */
export interface ProductWriteResult {
  id: number;
  name: string;
  description: string;
  price: string;
  condition: ProductCondition;
  quantity: number;
  location: string;
  category: number | null;
  status: ProductStatus;
}

export async function createProduct(payload: ProductWritePayload): Promise<ProductWriteResult> {
  const { data } = await client.post<ProductWriteResult>('/products/', payload);
  return data;
}

export async function updateProduct(
  id: number,
  payload: Partial<ProductWritePayload>,
): Promise<ProductWriteResult> {
  const { data } = await client.patch<ProductWriteResult>(`/products/${id}/`, payload);
  return data;
}

/** POST /api/products/{id}/images/ — append images (first becomes primary if none set). */
export async function uploadProductImages(id: number, uris: string[]): Promise<ProductImage[]> {
  if (uris.length === 0) {
    return [];
  }
  const form = new FormData();
  for (const uri of uris) {
    // The backend only accepts .jpg/.jpeg/.png/.webp/.gif — iOS pickers can
    // hand back HEIC, so force a .jpg name (Pillow still content-checks).
    form.append('images', {
      uri,
      name: `photo-${Date.now()}.jpg`,
      type: 'image/jpeg',
    } as unknown as Blob);
  }
  const { data } = await client.post<ProductImage[]>(`/products/${id}/images/`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

/** DELETE /api/products/{id}/images/{imageId}/ */
export async function deleteProductImage(id: number, imageId: number): Promise<void> {
  await client.delete(`/products/${id}/images/${imageId}/`);
}

export async function fetchCategories(): Promise<Category[]> {
  const { data } = await client.get<Category[]>('/categories/');
  return data;
}

export async function fetchFavorites(): Promise<Favorite[]> {
  const { data } = await client.get<Favorite[]>('/favorites/');
  return data;
}

export async function addFavorite(productId: number): Promise<void> {
  await client.post(`/favorites/${productId}/`);
}

export async function removeFavorite(productId: number): Promise<void> {
  await client.delete(`/favorites/${productId}/`);
}
