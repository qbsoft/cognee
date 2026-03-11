"use client";

import { useCallback, useState, FormEvent } from "react";

import apiFetch from "@/utils/fetch";
import { SearchIcon } from "@/ui/Icons";
import { LoadingIndicator } from "@/ui/App";

interface SearchResult {
  document_name?: string;
  text?: string;
  content?: string;
  score?: number;
  [key: string]: unknown;
}

interface SearchResponse {
  answer?: string;
  results?: SearchResult[];
}

const SEARCH_TYPES = [
  { value: "GRAPH_COMPLETION", label: "\u56FE\u8C31\u8865\u5168" },
  { value: "SUMMARIES", label: "\u6458\u8981\u641C\u7D22" },
  { value: "INSIGHTS", label: "\u6D1E\u5BDF\u641C\u7D22" },
  { value: "CHUNKS", label: "\u6587\u672C\u5757\u641C\u7D22" },
];

export default function SearchTab() {
  const [query, setQuery] = useState("");
  const [searchType, setSearchType] = useState(SEARCH_TYPES[0].value);
  const [answer, setAnswer] = useState<string | null>(null);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  const handleSubmit = useCallback(
    async (e: FormEvent) => {
      e.preventDefault();
      const trimmed = query.trim();
      if (!trimmed) return;

      setIsLoading(true);
      setError(null);
      setAnswer(null);
      setResults([]);
      setHasSearched(true);

      try {
        const response = await apiFetch("/v1/search", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: trimmed, search_type: searchType }),
        });
        const data: SearchResponse | SearchResult[] | string = await response.json();

        if (typeof data === "string") {
          setAnswer(data);
        } else if (Array.isArray(data)) {
          setResults(data);
        } else if (data && typeof data === "object") {
          if (data.answer) {
            setAnswer(data.answer);
          }
          if (Array.isArray(data.results)) {
            setResults(data.results);
          }
        }
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "\u641C\u7D22\u8BF7\u6C42\u5931\u8D25\uFF0C\u8BF7\u7A0D\u540E\u91CD\u8BD5";
        setError(message);
      } finally {
        setIsLoading(false);
      }
    },
    [query, searchType],
  );

  const formatScore = (score: number | undefined) => {
    if (score === undefined || score === null) return null;
    const displayScore = 1 - score;
    return displayScore.toFixed(3);
  };

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="max-w-4xl mx-auto">
        {/* Search Form */}
        <form onSubmit={handleSubmit} className="mb-6">
          <div className="flex items-center gap-3">
            <div className="relative flex-1">
              <div className="absolute left-4 top-1/2 -translate-y-1/2 pointer-events-none">
                <SearchIcon width={18} height={18} color="#9CA3AF" />
              </div>
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="\u8F93\u5165\u641C\u7D22\u95EE\u9898..."
                className="w-full h-12 pl-11 pr-4 rounded-xl border border-gray-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-shadow"
              />
            </div>
            <select
              value={searchType}
              onChange={(e) => setSearchType(e.target.value)}
              className="h-12 px-4 rounded-xl border border-gray-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            >
              {SEARCH_TYPES.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <button
              type="submit"
              disabled={isLoading || !query.trim()}
              className="h-12 px-6 rounded-xl bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
            >
              {isLoading ? (
                <>
                  <LoadingIndicator />
                  <span>\u641C\u7D22\u4E2D...</span>
                </>
              ) : (
                <span>\u641C\u7D22</span>
              )}
            </button>
          </div>
        </form>

        {/* Error State */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-4 text-red-700 text-sm">
            {error}
          </div>
        )}

        {/* Answer Display */}
        {answer && (
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4 mb-4">
            <h3 className="text-sm font-medium text-gray-500 mb-2">\u56DE\u7B54</h3>
            <p className="text-gray-800 whitespace-pre-wrap leading-relaxed">{answer}</p>
          </div>
        )}

        {/* Results List */}
        {results.length > 0 && (
          <div className="flex flex-col gap-3">
            <h3 className="text-sm font-medium text-gray-500">
              \u68C0\u7D22\u7ED3\u679C ({results.length})
            </h3>
            {results.map((result, index) => (
              <div
                key={index}
                className="bg-white rounded-xl border border-gray-100 shadow-sm p-4"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    {result.document_name && (
                      <p className="text-xs font-medium text-indigo-600 mb-1 truncate">
                        {result.document_name}
                      </p>
                    )}
                    <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
                      {result.text || result.content || JSON.stringify(result)}
                    </p>
                  </div>
                  {formatScore(result.score) !== null && (
                    <span className="shrink-0 text-xs font-mono text-gray-400 bg-gray-50 px-2 py-1 rounded">
                      {formatScore(result.score)}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Empty State */}
        {!isLoading && !error && !answer && results.length === 0 && (
          <div className="flex flex-col items-center justify-center py-24 text-gray-400">
            <SearchIcon width={64} height={64} color="#D1D5DB" />
            <p className="mt-4 text-sm">
              {hasSearched
                ? "\u672A\u627E\u5230\u76F8\u5173\u7ED3\u679C"
                : "\u8F93\u5165\u95EE\u9898\u5F00\u59CB\u641C\u7D22\u77E5\u8BC6\u5E93"}
            </p>
          </div>
        )}

        {/* Loading State (when no answer/results yet) */}
        {isLoading && !answer && results.length === 0 && (
          <div className="flex flex-col items-center justify-center py-24 text-gray-400">
            <LoadingIndicator />
            <p className="mt-4 text-sm">\u6B63\u5728\u641C\u7D22...</p>
          </div>
        )}
      </div>
    </div>
  );
}
