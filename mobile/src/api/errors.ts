/**
 * Consistent error extraction for the UI layer.
 *
 * Screens never call `Alert.alert`; they render a shared ErrorBanner / toast
 * fed by these helpers.
 */
import { isAxiosError } from 'axios';

import type { ApiErrorBody } from './types';

/**
 * Flatten a DRF error response into a human-readable message.
 * Field errors are rendered as `Field: message`; `detail` and
 * `non_field_errors` are used as-is.
 */
export function getErrorMessage(error: unknown): string {
  if (isAxiosError<ApiErrorBody>(error)) {
    const data = error.response?.data;
    if (data) {
      if (typeof data.detail === 'string' && data.detail) {
        return data.detail;
      }
      if (Array.isArray(data.non_field_errors) && data.non_field_errors.length > 0) {
        return data.non_field_errors[0];
      }
      for (const [field, value] of Object.entries(data)) {
        if (Array.isArray(value) && value.length > 0) {
          const message = String(value[0]);
          return field === 'password_confirmation' || field === 'password' || field === 'email'
            ? message
            : `${field}: ${message}`;
        }
      }
    }
    if (error.code === 'ECONNABORTED') {
      return 'The request timed out. Check your connection and try again.';
    }
    if (error.response) {
      return `Something went wrong (${error.response.status}).`;
    }
    if (error.request) {
      return 'Unable to reach the server. Check your connection and try again.';
    }
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'Something went wrong. Please try again.';
}
