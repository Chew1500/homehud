/** Shared shape for a single transcript entry rendered by ConversationThread. */
export interface ConversationTurn {
  id: string;
  role: 'user' | 'assistant';
  modality: 'voice' | 'text';
  text: string;
  /** Set on the first user turn after a conversation reset / TTL expiry. */
  divider?: { label: string; time: Date };
}
