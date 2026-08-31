/**
 * Unit tests for the Prompt 15 reviews API wrappers.
 */
import MockAdapter from 'axios-mock-adapter';
import * as SecureStore from 'expo-secure-store';

jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn(),
  setItemAsync: jest.fn(),
  deleteItemAsync: jest.fn(),
}));

import { createReview, fetchProductReviews, fetchSellerProfile } from '../src/api/reviews';
import { client } from '../src/api/client';

let mock: MockAdapter;

beforeEach(() => {
  jest.clearAllMocks();
  (SecureStore.getItemAsync as jest.Mock).mockResolvedValue(null);
  mock = new MockAdapter(client);
});

afterEach(() => {
  mock.restore();
});

const review = {
  id: 1,
  order_item: 9,
  buyer: { id: 2, full_name: 'Buyer' },
  product: 3,
  product_name: 'Laptop',
  rating: 5,
  comment: 'Great!',
  created_at: '2026-01-01T00:00:00Z',
};

describe('reviews API', () => {
  it('createReview posts to /reviews/', async () => {
    mock.onPost('/reviews/').reply(201, review);
    await expect(createReview({ order_item_id: 9, rating: 5, comment: 'Great!' })).resolves.toEqual(
      review,
    );
    expect(mock.history.post[0].data).toContain('order_item_id');
  });

  it('fetchProductReviews returns a paginated envelope', async () => {
    mock
      .onGet('/reviews/product/3/')
      .reply(200, { count: 1, next: null, previous: null, results: [review] });
    const page = await fetchProductReviews(3);
    expect(page.results).toHaveLength(1);
    expect(page.results[0].rating).toBe(5);
  });

  it('fetchSellerProfile returns aggregated seller data', async () => {
    mock.onGet('/reviews/seller/4/').reply(200, {
      seller: {
        id: 4,
        email: 's@x.com',
        full_name: 'Seller',
        profile_picture: null,
        average_rating: 4.5,
        rating_count: 2,
      },
      average_rating: 4.5,
      rating_count: 2,
      reviews: { count: 2, next: null, previous: null, results: [review] },
    });
    const profile = await fetchSellerProfile(4);
    expect(profile.average_rating).toBe(4.5);
    expect(profile.rating_count).toBe(2);
  });
});
