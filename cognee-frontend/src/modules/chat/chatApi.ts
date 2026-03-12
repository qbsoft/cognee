import { fetch as apiFetch } from "@/utils";

export interface ChatSession {
  id: string;
  dataset_id: string | null;
  search_type: string;
  title: string;
  created_at: string;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

const BASE = "/v1/chat";

export async function listSessions(): Promise<ChatSession[]> {
  const res = await apiFetch(`${BASE}/sessions`);
  return res.json();
}

export async function createSession(params: {
  dataset_id?: string | null;
  search_type: string;
  title?: string;
}): Promise<ChatSession> {
  const res = await apiFetch(`${BASE}/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  return res.json();
}

export async function deleteSession(sessionId: string): Promise<void> {
  await apiFetch(`${BASE}/sessions/${sessionId}`, { method: "DELETE" });
}

export async function listMessages(sessionId: string): Promise<ChatMessage[]> {
  const res = await apiFetch(`${BASE}/sessions/${sessionId}/messages`);
  return res.json();
}

export async function addMessage(
  sessionId: string,
  role: "user" | "assistant",
  content: string
): Promise<ChatMessage> {
  const res = await apiFetch(`${BASE}/sessions/${sessionId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role, content }),
  });
  return res.json();
}
