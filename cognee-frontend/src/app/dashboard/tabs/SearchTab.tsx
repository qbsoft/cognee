"use client";

import { useCallback, useState, FormEvent } from "react";
import { useTranslation } from "react-i18next";

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

const SEARCH_TYPE_KEYS = [
  { value: "GRAPH_COMPLETION", tKey: "dashboard.search.types.GRAPH_COMPLETION" },
  { value: "SUMMARIES", tKey: "dashboard.search.types.SUMMARIES" },
  { value: "INSIGHTS", tKey: "dashboard.search.types.INSIGHTS" },
  { value: "CHUNKS", tKey: "dashboard.search.types.CHUNKS" },
];

export default function SearchTab() {
  const { t } = useTranslation();
  const [query, setQuery] = useState("");
  const [searchType, setSearchType] = useState(SEARCH_TYPE_KEYS[0].value);
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
          err instanceof Error ? err.message : t("dashboard.search.errorFallback");
        setError(message);
      } finally {
        setIsLoading(false);
      }
    },
    [query, searchType, t],
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
                placeholder={t("dashboard.search.placeholder")}
                className="w-full h-12 pl-11 pr-4 rounded-xl border border-gray-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-shadow"
              />
            </div>
            <select
              value={searchType}
              onChange={(e) => setSearchType(e.target.value)}
              className="h-12 px-4 rounded-xl border border-gray-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            >
              {SEARCH_TYPE_KEYS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {t(opt.tKey)}
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
                  <span>{t("dashboard.search.searching")}</span>
                </>
              ) : (
                <span>{t("dashboard.search.searchButton")}</span>
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
            <h3 className="text-sm font-medium text-gray-500 mb-2">{t("dashboard.search.answerLabel")}</h3>
            <p className="text-gray-800 whitespace-pre-wrap leading-relaxed">{answer}</p>
          </div>
        )}

        {/* Results List */}
        {results.length > 0 && (
          <div className="flex flex-col gap-3">
            <h3 className="text-sm font-medium text-gray-500">
              {t("dashboard.search.resultsLabel", { count: results.length })}
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
                ? t("dashboard.search.noResults")
                : t("dashboard.search.emptyHint")}
            </p>
          </div>
        )}

        {/* Loading State (when no answer/results yet) */}
        {isLoading && !answer && results.length === 0 && (
          <div className="flex flex-col items-center justify-center py-24 text-gray-400">
            <LoadingIndicator />
            <p className="mt-4 text-sm">{t("dashboard.search.searching")}</p>
          </div>
        )}
      </div>
    </div>
  );
}
