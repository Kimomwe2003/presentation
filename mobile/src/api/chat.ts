/**
 * Typed wrappers around the Prompt 13 chat API.
 *
 * Delivery is client-side polling: the app calls fetchMessages on a timer while
 * the conversation screen is focused. The backend stores the ordering data the
 * UI needs (conversation + created_at + id) for newest-first history with
 * load-more, and the list endpoints expose unread counts.
 */
import { client } from './client';
import type { ChatMessage, Conversation, MessagePage } from './types';

/** The caller's conversations, most recently active first. */
export async function fetchConversations(): Promise<Conversation[]> {
  const { data } = await client.get<{ results?: Conversation[] }>('/chats/');
  if (Array.isArray(data)) {
    return data;
  }
  return data.results ?? [];
}

/** Get-or-create a conversation from a product (its seller is the counterpart). */
export async function openConversationForProduct(productId: number): Promise<Conversation> {
  const { data } = await client.post<Conversation>('/chats/', { product_id: productId });
  return data;
}

/** Send a message in a conversation. */
export async function sendMessage(conversationId: number, body: string): Promise<ChatMessage> {
  const { data } = await client.post<ChatMessage>(`/chats/${conversationId}/messages/`, {
    body,
  });
  return data;
}

interface FetchMessagesOptions {
  page?: number;
  pageSize?: number;
}

/** Fetch a page of message history (newest first). */
export async function fetchMessages(
  conversationId: number,
  options: FetchMessagesOptions = {},
): Promise<MessagePage> {
  const { data } = await client.get<MessagePage>(`/chats/${conversationId}/messages/`, {
    params: {
      page: options.page ?? 1,
      page_size: options.pageSize ?? 50,
    },
  });
  return data;
}

/** Poll for the newest messages, appending any that are newer than `newestId`. */
export async function pollNewMessages(
  conversationId: number,
  newestId: number | null,
): Promise<ChatMessage[]> {
  const page = await fetchMessages(conversationId, { page: 1, pageSize: 50 });
  if (newestId == null) {
    return [...page.results].reverse();
  }
  const fresh = [] as ChatMessage[];
  for (const message of page.results) {
    if (message.id > newestId) {
      fresh.unshift(message);
    } else {
      break;
    }
  }
  return fresh;
}

/** Mark all of a conversation's inbound messages as read. */
export async function markConversationRead(conversationId: number): Promise<void> {
  await client.post(`/chats/${conversationId}/read/`);
}
