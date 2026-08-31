import { useState } from 'react';
import { KeyboardAvoidingView, Platform, StyleSheet, Text, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { createReview } from '../../api/reviews';
import { getErrorMessage } from '../../api/errors';
import Button from '../../components/Button';
import Card from '../../components/Card';
import StarRatingInput from '../../components/StarRatingInput';
import TextInput from '../../components/TextInput';
import { useToast } from '../../context/ToastContext';
import type { RootStackParamList } from '../../navigation/types';
import { colors, spacing, typography } from '../../theme';

type Props = NativeStackScreenProps<RootStackParamList, 'Review'>;

export default function ReviewScreen({ route, navigation }: Props) {
  const { orderItemId, productName } = route.params;
  const { showToast } = useToast();

  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const canSubmit = rating > 0 && !submitting;

  const handleSubmit = async () => {
    if (rating === 0) {
      return;
    }
    setSubmitting(true);
    try {
      await createReview({ order_item_id: orderItemId, rating, comment: comment.trim() });
      showToast('Review submitted — thank you!', { type: 'success' });
      navigation.goBack();
    } catch (e) {
      showToast(getErrorMessage(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <View style={styles.container}>
        <Card style={styles.card}>
          <Text style={styles.heading}>Rate this purchase</Text>
          {productName ? <Text style={styles.product}>{productName}</Text> : null}
          <Text style={styles.prompt}>How was your experience?</Text>
          <View style={styles.starsWrap}>
            <StarRatingInput value={rating} onChange={setRating} />
          </View>
          {rating > 0 ? (
            <Text style={styles.ratingLabel}>{rating} / 5</Text>
          ) : (
            <Text style={styles.ratingHint}>Tap a star to rate</Text>
          )}
        </Card>

        <Card style={styles.card}>
          <Text style={styles.label}>Comment (optional)</Text>
          <TextInput
            value={comment}
            onChangeText={setComment}
            placeholder="Share your thoughts about the purchase"
            multiline
            maxLength={2000}
            textAlignVertical="top"
          />
        </Card>

        <Button
          title="Submit review"
          loading={submitting}
          disabled={!canSubmit}
          onPress={() => void handleSubmit()}
        />
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  flex: {
    flex: 1,
    backgroundColor: colors.background,
  },
  container: {
    flex: 1,
    backgroundColor: colors.background,
    padding: spacing.lg,
    gap: spacing.lg,
  },
  card: {
    gap: spacing.sm,
  },
  heading: {
    ...typography.title,
    fontSize: 20,
  },
  product: {
    ...typography.body,
    fontWeight: '600',
  },
  prompt: {
    ...typography.label,
  },
  starsWrap: {
    alignItems: 'center',
    marginVertical: spacing.sm,
  },
  ratingLabel: {
    ...typography.body,
    textAlign: 'center',
    color: colors.primary,
    fontWeight: '600',
  },
  ratingHint: {
    ...typography.label,
    textAlign: 'center',
  },
  label: {
    ...typography.subtitle,
  },
});
