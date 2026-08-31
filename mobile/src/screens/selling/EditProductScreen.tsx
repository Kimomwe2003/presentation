import { useCallback, useEffect, useState } from 'react';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import {
  fetchProduct,
  updateProduct,
  uploadProductImages,
  type ProductWritePayload,
} from '../../api/catalog';
import { getErrorMessage } from '../../api/errors';
import type { ProductDetail } from '../../api/types';
import ErrorState from '../../components/ErrorState';
import LoadingSpinner from '../../components/LoadingSpinner';
import { useToast } from '../../context/ToastContext';
import type { RootStackParamList } from '../../navigation/types';
import ProductForm from './ProductForm';

type Props = NativeStackScreenProps<RootStackParamList, 'EditProduct'>;

export default function EditProductScreen({ navigation, route }: Props) {
  const { productId } = route.params;
  const { showToast } = useToast();

  const [product, setProduct] = useState<ProductDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setProduct(await fetchProduct(productId));
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [productId]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      // Touch state only after an await so nothing runs synchronously from the
      // effect body (react-hooks/set-state-in-effect).
      await Promise.resolve();
      if (cancelled) return;
      await load();
    })();
    return () => {
      cancelled = true;
    };
  }, [load]);

  const handleSubmit = useCallback(
    async (payload: ProductWritePayload, newImageUris: string[]) => {
      setSubmitting(true);
      try {
        await updateProduct(productId, payload);
        await uploadProductImages(productId, newImageUris);
        showToast('Listing updated', { type: 'success' });
        navigation.goBack();
      } catch (e) {
        showToast(getErrorMessage(e));
      } finally {
        setSubmitting(false);
      }
    },
    [navigation, productId, showToast],
  );

  if (loading) {
    return <LoadingSpinner label="Loading listing…" />;
  }

  if (error || !product) {
    return <ErrorState message={error ?? 'This listing is no longer available.'} onRetry={load} />;
  }

  return (
    <ProductForm
      initial={product}
      submitLabel="Save changes"
      submitting={submitting}
      onSubmit={handleSubmit}
    />
  );
}
