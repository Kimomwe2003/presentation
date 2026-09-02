import type { ProductCondition } from '../api/types';

/** Condition codes from the backend, mapped to display labels. */
export const CONDITION_LABELS: Record<ProductCondition, string> = {
  NEW: 'New',
  LIKE_NEW: 'Like new',
  GOOD: 'Good',
  FAIR: 'Fair',
  USED: 'Used',
};

/** Listing status codes -> display labels (seller dashboard). */
export const PRODUCT_STATUS_LABELS: Record<string, string> = {
  DRAFT: 'Draft',
  ACTIVE: 'Active',
  INACTIVE: 'Inactive',
  SOLD: 'Sold',
};

/**
 * Format a backend decimal string ("150.00") with thousands separators.
 * Hermes Intl support is incomplete, so grouping is done manually.
 */
export function formatPrice(price: string | number): string {
  const [whole, decimals] = String(price).split('.');
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  return decimals && Number(decimals) > 0 ? `${grouped}.${decimals}` : grouped;
}

/** Relative time ("5m ago", "3h ago", "2d ago"). */
export function formatRelativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  const now = Date.now();
  const seconds = Math.max(0, Math.floor((now - then) / 1000));

  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  const weeks = Math.floor(days / 7);
  if (weeks < 5) return `${weeks}w ago`;
  return new Date(iso).toLocaleDateString();
}

/** Initials for avatar placeholders. */
export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  return (parts[0][0] + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase();
}

/**
 * Ensures an image URL is an absolute, HTTPS URL reachable by the mobile app.
 * Resolves relative media paths and converts local http endpoints / ngrok http URLs to https.
 */
export function resolveImageUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  const trimmed = url.trim();
  if (!trimmed) return null;

  const rawApiUrl = process.env.EXPO_PUBLIC_API_URL ?? '';
  let apiHost = '';
  try {
    if (rawApiUrl) {
      const parsed = new URL(rawApiUrl);
      apiHost = `${parsed.protocol}//${parsed.host}`;
    }
  } catch {
    // Fallback if URL parsing fails
  }

  // Relative path (e.g. /media/products/... or media/products/...)
  if (trimmed.startsWith('/media/') || trimmed.startsWith('media/')) {
    const cleanPath = trimmed.startsWith('/') ? trimmed : `/${trimmed}`;
    return apiHost ? `${apiHost}${cleanPath}` : cleanPath;
  }

  // Replace any http:// with https:// for ngrok or remote domains to prevent ATS / Mixed Content blocks
  if (trimmed.startsWith('http://')) {
    if (trimmed.includes('ngrok-free.dev') || trimmed.includes('ngrok-free.app')) {
      return trimmed.replace('http://', 'https://');
    }
    if (apiHost && (trimmed.includes('localhost') || trimmed.includes('127.0.0.1') || trimmed.includes('192.168.') || trimmed.includes('172.20.') || trimmed.includes('172.') || trimmed.includes('10.'))) {
      const pathIndex = trimmed.indexOf('/media/');
      if (pathIndex !== -1) {
        return `${apiHost}${trimmed.substring(pathIndex)}`;
      }
      return trimmed;
    }
    return trimmed.replace('http://', 'https://');
  }

  return trimmed;
}
