/**
 * Typed wrappers around the Prompt 15 reviews API.
 *
 * Review creation is restricted server-side to the buyer of a COMPLETED order
 * item, so the client can rely on the backend for the completed-purchase gate.
 */
import { client } from './client';
import type { Paginated, Review, ReviewPayload, SellerProfile } from './types';

/** Create a review for a completed order item. */
export async function createReview(payload: ReviewPayload): Promise<Review> {
  const { data } = await client.post<Review>('/reviews/', payload);
  return data;
}

/** Paginated reviews for a product. */
export async function fetchProductReviews(productId: number): Promise<Paginated<Review>> {
  const { data } = await client.get<Paginated<Review>>(`/reviews/product/${productId}/`);
  return data;
}

/** A seller's public profile with aggregated rating + reviews. */
export async function fetchSellerProfile(userId: number): Promise<SellerProfile> {
  const { data } = await client.get<SellerProfile>(`/reviews/seller/${userId}/`);
  return data;
}
