import { useCallback, useState } from 'react';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { createProduct, uploadProductImages, type ProductWritePayload } from '../../api/catalog';
import { getErrorMessage } from '../../api/errors';
import { useToast } from '../../context/ToastContext';
import type { RootStackParamList } from '../../navigation/types';
import ProductForm from './ProductForm';

type Props = NativeStackScreenProps<RootStackParamList, 'AddProduct'>;

export default function AddProductScreen({ navigation }: Props) {
  const { showToast } = useToast();
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = useCallback(
    async (payload: ProductWritePayload, newImageUris: string[]) => {
      setSubmitting(true);
      try {
        const product = await createProduct(payload);
        await uploadProductImages(product.id, newImageUris);
        showToast(payload.status === 'ACTIVE' ? 'Listing published' : 'Draft saved', {
          type: 'success',
        });
        navigation.goBack();
      } catch (e) {
        showToast(getErrorMessage(e));
      } finally {
        setSubmitting(false);
      }
    },
    [navigation, showToast],
  );

  return (
    <ProductForm submitLabel="Create listing" submitting={submitting} onSubmit={handleSubmit} />
  );
}
