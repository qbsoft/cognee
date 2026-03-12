"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { fetch as apiFetch } from "@/utils";
import useDatasets from "@/modules/ingestion/useDatasets";
import {
  listSessions,
  createSession,
  deleteSession,
  listMessages,
  addMessage,
  type ChatSession,
  type ChatMessage,
} from "@/modules/chat/chatApi";

// ── Types ─────────────────────────────────────────────────────────────────────

type SearchType = "GRAPH_COMPLETION" | "CHUNKS";

// ── Icons ─────────────────────────────────────────────────────────────────────

function SendIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
    </svg>
  );
}

function HistoryIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
    </svg>
  );
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatRelativeTime(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffH = Math.floor(diffMs / 3600000);
  if (diffH < 1) return "刚刚";
  if (diffH < 24) return `${diffH} 小时前`;
  const diffD = Math.floor(diffH / 24);
  if (diffD === 1) return "昨天";
  return `${diffD} 天前`;
}

function parseSearchResponse(data: unknown): string {
  if (typeof data === "string") return data;
  if (Array.isArray(data)) {
    if (data.length === 0) return "未找到相关内容。";
    if (typeof data[0] === "string") return data[0];
    return data
      .map((item: { text?: string; content?: string }) =>
        item.text || item.content || JSON.stringify(item)
      )
      .join("\n\n");
  }
  if (data && typeof data === "object") {
    const obj = data as { answer?: string; results?: unknown[] };
    if (obj.answer) return obj.answer;
    if (Array.isArray(obj.results)) return parseSearchResponse(obj.results);
  }
  return String(data);
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function SearchTab() {
  const { t } = useTranslation();
  const { datasets } = useDatasets();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Toolbar state
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>("");
  const [searchType, setSearchType] = useState<SearchType>("GRAPH_COMPLETION");

  // Session state
  const [currentSession, setCurrentSession] = useState<ChatSession | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // History dropdown
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const historyRef = useRef<HTMLDivElement>(null);

  // Input
  const [input, setInput] = useState("");

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Set default dataset
  useEffect(() => {
    if (datasets.length > 0 && !selectedDatasetId) {
      setSelectedDatasetId(datasets[0].id);
    }
  }, [datasets, selectedDatasetId]);

  // Close history dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (historyRef.current && !historyRef.current.contains(e.target as Node)) {
        setIsHistoryOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  // Load history sessions list
  const loadSessions = useCallback(async () => {
    try {
      const data = await listSessions();
      setSessions(data);
    } catch {
      // Silently fail
    }
  }, []);

  // Open a historical session
  const openSession = useCallback(async (session: ChatSession) => {
    setCurrentSession(session);
    setIsHistoryOpen(false);
    setSearchType(session.search_type as SearchType);
    if (session.dataset_id) setSelectedDatasetId(session.dataset_id);
    try {
      const msgs = await listMessages(session.id);
      setMessages(msgs);
    } catch {
      setMessages([]);
    }
  }, []);

  // Start a new session
  const startNewSession = useCallback(() => {
    setCurrentSession(null);
    setMessages([]);
    setInput("");
  }, []);

  // Delete a session
  const handleDeleteSession = useCallback(async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await deleteSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      if (currentSession?.id === sessionId) startNewSession();
    } catch {
      // Silently fail
    }
  }, [currentSession, startNewSession]);

  // Send a message
  const handleSend = useCallback(async () => {
    const trimmed = input.trim();
    if (!trimmed || isLoading) return;

    setInput("");
    setIsLoading(true);

    const dataset = datasets.find((d) => d.id === selectedDatasetId);
    const datasetName = dataset?.name ?? "main_dataset";

    // Create session on first message
    let session = currentSession;
    if (!session) {
      try {
        session = await createSession({
          dataset_id: selectedDatasetId || null,
          search_type: searchType,
          title: trimmed.slice(0, 20),
        });
        setCurrentSession(session);
      } catch {
        setIsLoading(false);
        return;
      }
    }

    // Optimistic user message
    const optimisticUser: ChatMessage = {
      id: crypto.randomUUID(),
      session_id: session.id,
      role: "user",
      content: trimmed,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimisticUser]);

    // Persist user message
    try {
      await addMessage(session.id, "user", trimmed);
    } catch {
      // Continue even if persistence fails
    }

    // Call search API
    try {
      const res = await apiFetch("/v1/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: trimmed,
          search_type: searchType,
          datasets: [datasetName],
          top_k: 10,
        }),
      });
      const data = await res.json();
      const answerText = parseSearchResponse(data);

      const assistantMsg: ChatMessage = {
        id: crypto.randomUUID(),
        session_id: session.id,
        role: "assistant",
        content: answerText,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMsg]);

      // Persist assistant message
      await addMessage(session.id, "assistant", answerText);

      // Refresh session list (title may have updated)
      await loadSessions();
    } catch {
      const errMsg: ChatMessage = {
        id: crypto.randomUUID(),
        session_id: session.id,
        role: "assistant",
        content: t("dashboard.search.errorFallback"),
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setIsLoading(false);
    }
  }, [input, isLoading, currentSession, selectedDatasetId, searchType, datasets, t, loadSessions]);

  // Enter to send, Shift+Enter for newline
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  return (
    <div className="h-full flex flex-col">
      {/* ── Toolbar ─────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3 px-6 py-3 border-b border-gray-100 bg-white shrink-0">
        {/* Dataset selector */}
        {datasets.length > 0 ? (
          <div className="relative">
            <select
              value={selectedDatasetId}
              onChange={(e) => setSelectedDatasetId(e.target.value)}
              disabled={!!currentSession}
              className="appearance-none pl-3 pr-8 h-9 text-sm rounded-lg border border-gray-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-300 cursor-pointer max-w-[180px] truncate disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {datasets.map((ds) => (
                <option key={ds.id} value={ds.id}>{ds.name}</option>
              ))}
            </select>
            <div className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-gray-400">
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </div>
          </div>
        ) : (
          <span className="text-sm text-gray-400">{t("dashboard.search.noDatasets")}</span>
        )}

        {/* Search type segmented control */}
        <div className="flex rounded-lg border border-gray-200 overflow-hidden shrink-0">
          {(
            [
              { value: "GRAPH_COMPLETION", label: t("dashboard.search.modeDeep") },
              { value: "CHUNKS", label: t("dashboard.search.modeFast") },
            ] as { value: SearchType; label: string }[]
          ).map(({ value, label }) => (
            <button
              key={value}
              type="button"
              disabled={!!currentSession}
              onClick={() => setSearchType(value)}
              className={`px-4 h-9 text-xs font-medium transition-colors disabled:opacity-60 disabled:cursor-not-allowed ${
                searchType === value
                  ? "bg-indigo-600 text-white"
                  : "bg-white text-gray-500 hover:bg-gray-50"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Spacer */}
        <div className="flex-1" />

        {/* History dropdown */}
        <div className="relative" ref={historyRef}>
          <button
            type="button"
            onClick={() => { loadSessions(); setIsHistoryOpen((v) => !v); }}
            className="flex items-center gap-1.5 h-9 px-3 text-sm text-gray-500 hover:text-indigo-600 border border-gray-200 rounded-lg hover:border-indigo-300 transition-colors"
          >
            <HistoryIcon />
            <span>{t("dashboard.search.history")}</span>
          </button>

          {isHistoryOpen && (
            <div className="absolute right-0 top-11 w-72 bg-white rounded-xl border border-gray-100 shadow-lg z-20 overflow-hidden">
              <div className="px-4 py-2.5 border-b border-gray-50">
                <span className="text-xs font-medium text-gray-500">{t("dashboard.search.historyTitle")}</span>
              </div>
              {sessions.length === 0 ? (
                <div className="px-4 py-6 text-center text-sm text-gray-400">
                  {t("dashboard.search.noHistory")}
                </div>
              ) : (
                <div className="max-h-64 overflow-y-auto">
                  {sessions.map((s) => (
                    <div
                      key={s.id}
                      onClick={() => openSession(s)}
                      className={`flex items-center justify-between px-4 py-3 hover:bg-gray-50 cursor-pointer group ${
                        currentSession?.id === s.id ? "bg-indigo-50" : ""
                      }`}
                    >
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-gray-700 truncate">{s.title}</p>
                        <p className="text-xs text-gray-400 mt-0.5">{formatRelativeTime(s.created_at)}</p>
                      </div>
                      <button
                        onClick={(e) => handleDeleteSession(s.id, e)}
                        className="opacity-0 group-hover:opacity-100 ml-2 text-gray-300 hover:text-red-400 transition-all"
                      >
                        <TrashIcon />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* New chat button */}
        <button
          type="button"
          onClick={startNewSession}
          className="h-9 px-4 text-sm font-medium text-indigo-600 border border-indigo-200 rounded-lg hover:bg-indigo-50 transition-colors"
        >
          + {t("dashboard.search.newChat")}
        </button>
      </div>

      {/* ── Messages area ───────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
        {/* Empty / welcome state */}
        {messages.length === 0 && !isLoading && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-14 h-14 rounded-2xl bg-indigo-50 flex items-center justify-center text-indigo-500 mb-4 text-2xl">
              🧠
            </div>
            <h3 className="text-base font-semibold text-gray-700 mb-1">
              {t("dashboard.search.welcomeTitle")}
            </h3>
            <p className="text-sm text-gray-400 max-w-sm">
              {t("dashboard.search.welcomeHint")}
            </p>
          </div>
        )}

        {/* Messages */}
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            {msg.role === "assistant" && (
              <div className="w-7 h-7 rounded-full bg-indigo-100 flex items-center justify-center text-sm mr-2 shrink-0 mt-0.5">
                🧠
              </div>
            )}
            <div
              className={`max-w-2xl px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
                msg.role === "user"
                  ? "bg-indigo-600 text-white rounded-tr-sm"
                  : "bg-white border border-gray-100 text-gray-800 shadow-sm rounded-tl-sm"
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}

        {/* Loading bubble */}
        {isLoading && (
          <div className="flex justify-start">
            <div className="w-7 h-7 rounded-full bg-indigo-100 flex items-center justify-center text-sm mr-2 shrink-0">
              🧠
            </div>
            <div className="bg-white border border-gray-100 shadow-sm rounded-2xl rounded-tl-sm px-4 py-3 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce [animation-delay:0ms]" />
              <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce [animation-delay:150ms]" />
              <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce [animation-delay:300ms]" />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* ── Input bar ───────────────────────────────────────────────── */}
      <div className="shrink-0 px-6 py-4 border-t border-gray-100 bg-white">
        <div className="flex items-end gap-3 max-w-4xl mx-auto">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t("dashboard.search.inputPlaceholder")}
            rows={1}
            className="flex-1 resize-none rounded-xl border border-gray-200 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-300 bg-gray-50 focus:bg-white transition-colors max-h-32 overflow-y-auto"
            style={{ height: "auto" }}
            onInput={(e) => {
              const el = e.currentTarget;
              el.style.height = "auto";
              el.style.height = `${Math.min(el.scrollHeight, 128)}px`;
            }}
          />
          <button
            type="button"
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="w-10 h-10 rounded-xl bg-indigo-600 text-white flex items-center justify-center hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shrink-0"
          >
            <SendIcon />
          </button>
        </div>
        <p className="text-xs text-gray-400 text-center mt-2">{t("dashboard.search.inputHint")}</p>
      </div>
    </div>
  );
}
