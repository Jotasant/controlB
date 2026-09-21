export interface ChatProvider {
  code: string;
  name: string;
}

export interface ChatInstanceDetails {
  instance_id: string | null;
  instance_name: string;
  phone: string | null;
  profile_name: string | null;
  integration: string | null;
  state: ChatConnectionStatus;
  message_count: number | null;
  chat_count: number | null;
  local_message_count: number;
  local_conversation_count: number;
  last_webhook_at: string | null;
}

export interface ChatHistoryResult {
  imported: number;
  existing: number;
  skipped: number;
  scanned: number;
  total: number;
  next_page: number | null;
  snapshot_at: string;
}

export interface ChatChannel {
  id: string;
  name: string;
  provider: string;
  status: string;
  team_id: string;
  instance_phone: string | null;
}

export type ChatConnectionStatus = 'DISCONNECTED' | 'CONNECTING' | 'CONNECTED' | 'ERROR';

export interface ChatConnection {
  groups_enabled: boolean;
  transcription_enabled: boolean;
  id: string;
  member_ids: string[];
  team_id: string | null;
  instance_phone: string | null;
  provider_instance_id: string | null;
  organization_id: string;
  provider: string;
  name: string;
  base_url: string;
  external_instance_id: string;
  credentials_hint: string | null;
  configuration: Record<string, unknown>;
  status: ChatConnectionStatus;
  last_error: string | null;
  last_synced_at: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ChatConnectionCreatePayload {
  groups_enabled?: boolean;
  transcription_enabled?: boolean;
  member_ids: string[];
  provider?: string;
  name: string;
  base_url: string;
  external_instance_id: string;
  api_key: string;
  webhook_secret?: string;
  is_active?: boolean;
}

export interface ChatConnectionUpdatePayload {
  groups_enabled?: boolean;
  transcription_enabled?: boolean;
  member_ids?: string[];
  name?: string;
  base_url?: string;
  external_instance_id?: string;
  api_key?: string;
  webhook_secret?: string;
  is_active?: boolean;
}

export interface ChatInstanceProvision {
  created: boolean;
  already_existed: boolean;
  qr_code_base64: string | null;
  pairing_code: string | null;
  connection: ChatConnection;
}

export interface ChatPairing {
  qr_code_base64: string | null;
  pairing_code: string | null;
  state: ChatConnectionStatus;
  connection: ChatConnection;
}

export interface ChatLink {
  id: string;
  business_document_id: string;
  link_type: string;
  is_primary: boolean;
}

export interface ChatConversation {
  is_group: boolean;
  assigned_user_name: string | null;
  id: string;
  organization_id: string;
  connection_id: string;
  team_id: string | null;
  instance_phone: string | null;
  is_archived: boolean;
  closed_at: string | null;
  closed_by_id: string | null;
  external_chat_id: string;
  remote_phone: string;
  display_name: string | null;
  avatar_url: string | null;
  contact_id: string | null;
  customer_id: string | null;
  assigned_user_id: string | null;
  status: 'OPEN' | 'CLOSED';
  unread_count: number;
  last_message_preview: string | null;
  last_message_at: string | null;
  created_at: string;
  updated_at: string;
  document_links: ChatLink[];
}

export interface ChatMessage {
  deleted_at: string | null;
  revoke_status: string | null;
  sender_external_id: string | null;
  created_by_id: string | null;
  author_name: string | null;
  transcription: string | null;
  transcription_status: 'NOT_REQUESTED' | 'NOT_CONFIGURED' | 'PENDING' | 'DONE' | 'FAILED';
  id: string;
  organization_id: string;
  conversation_id: string;
  external_message_id: string | null;
  client_request_id: string | null;
  direction: 'INBOUND' | 'OUTBOUND';
  message_type: string;
  content: string | null;
  media_url: string | null;
  media_mime_type: string | null;
  media_filename: string | null;
  status: string;
  sender_name: string | null;
  sender_phone: string | null;
  error_message: string | null;
  occurred_at: string;
  delivered_at: string | null;
  read_at: string | null;
  created_at: string;
  reply_to_message_id?: string | null;
  reply_snapshot?: {
    id?: string | null;
    external_message_id?: string | null;
    text?: string | null;
    sender_name?: string | null;
    message_type?: string | null;
  } | null;
  reactions?: Array<{
    emoji: string;
    user_id?: string;
    user_name?: string;
    sender?: string;
    from_me?: boolean;
  }>;
}

export interface ChatConversationPage {
  items: ChatConversation[];
  total: number;
  page: number;
  page_size: number;
}

export interface ChatMessagePage {
  items: ChatMessage[];
  total: number;
  page: number;
  page_size: number;
}

export interface ChatConversationFilters {
  page?: number;
  page_size?: number;
  search?: string;
  document_id?: string;
  status?: 'OPEN' | 'CLOSED';
  archived?: boolean;
  unlinked?: boolean;
  mine?: boolean;
  assigned_user_id?: string | null;
}

export interface ContactOrigin {
  id: string;
  name: string;
  description?: string | null;
  channel_type: string;
  is_active: boolean;
}

export interface ChatContact {
  id: string;
  name: string;
  phone: string | null;
  origin_id: string | null;
  origin_name: string | null;
}

export interface ChatConversationUpdate {
  status?: 'OPEN' | 'CLOSED';
  is_archived?: boolean;
  assigned_user_id?: string | null;
}

export interface ChatNotificationItem {
  id: string;
  conversation_id: string;
  title: string;
  sender_name: string | null;
  received_at: string;
}

export interface ChatNotificationPage {
  items: ChatNotificationItem[];
  unread_count: number;
  until: string;
  next_page: number | null;
}
