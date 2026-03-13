"use client";

import { useCallback, useEffect, useRef, useState, MutableRefObject } from "react";
import { useTranslation } from "react-i18next";
import { fetch } from "@/utils";

import GraphVisualization, { GraphVisualizationAPI } from "../../(graph)/GraphVisualization";
import type { GraphControlsAPI } from "../../(graph)/GraphControls";
import GraphLegend from "../../(graph)/GraphLegend";
import useDatasets from "@/modules/ingestion/useDatasets";
import getDatasetGraph from "@/modules/datasets/getDatasetGraph";

interface GraphNode {
  id: string | number;
  label: string;
  type?: string;
  properties?: object;
}

interface GraphData {
  nodes: GraphNode[];
  links: { source: string | number; target: string | number; label: string }[];
}

type SearchMode = "explore" | "ask";

// BFS: compute N-hop subgraph from nodes whose label matches the query
function computeSubgraph(fullData: GraphData, query: string, hops: number): GraphData {
  const lower = query.toLowerCase();
  const seedIds = new Set<string | number>(
    fullData.nodes
      .filter((n) => String(n.label).toLowerCase().includes(lower))
      .map((n) => n.id),
  );

  if (seedIds.size === 0) return fullData;

  const visited = new Set<string | number>(seedIds);
  let frontier = new Set<string | number>(seedIds);

  for (let i = 0; i < hops; i++) {
    const next = new Set<string | number>();
    for (const link of fullData.links) {
      const src =
        typeof link.source === "object"
          ? (link.source as GraphNode).id
          : link.source;
      const tgt =
        typeof link.target === "object"
          ? (link.target as GraphNode).id
          : link.target;
      if (frontier.has(src) && !visited.has(tgt)) next.add(tgt);
      if (frontier.has(tgt) && !visited.has(src)) next.add(src);
    }
    next.forEach((id) => visited.add(id));
    frontier = next;
  }

  return {
    nodes: fullData.nodes.filter((n) => visited.has(n.id)),
    links: fullData.links.filter((l) => {
      const src =
        typeof l.source === "object" ? (l.source as GraphNode).id : l.source;
      const tgt =
        typeof l.target === "object" ? (l.target as GraphNode).id : l.target;
      return visited.has(src) && visited.has(tgt);
    }),
  };
}

function RefreshIcon({ spinning }: { spinning?: boolean }) {
  return (
    <svg
      className={`w-4 h-4 ${spinning ? "animate-spin" : ""}`}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
      />
    </svg>
  );
}

export default function GraphTab() {
  const { t } = useTranslation();
  const { datasets, refreshDatasets } = useDatasets();
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>("");
  const [data, setData] = useState<GraphData>();
  const [isLoading, setIsLoading] = useState(false);

  const graphRef = useRef<GraphVisualizationAPI>();
  const graphControls = useRef<GraphControlsAPI>();

  // Search state
  const [searchQuery, setSearchQuery] = useState("");
  const [searchMode, setSearchMode] = useState<SearchMode>("explore");
  const [hops, setHops] = useState<1 | 2>(1);
  const [displayData, setDisplayData] = useState<GraphData | undefined>();
  const [highlightedNodeIds, setHighlightedNodeIds] = useState<Set<string | number>>(new Set());

  // Answer panel state
  const [isPanelOpen, setIsPanelOpen] = useState(false);
  const [currentQuestion, setCurrentQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [isAnswering, setIsAnswering] = useState(false);
  const [relatedNodes, setRelatedNodes] = useState<GraphNode[]>([]);

  // Initial load
  useEffect(() => {
    refreshDatasets().then((fetched) => {
      if (fetched?.length) {
        setSelectedDatasetId(fetched[0].id);
      }
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadGraph = useCallback(async (datasetId: string) => {
    setIsLoading(true);
    setSearchQuery("");
    setDisplayData(undefined);
    setHighlightedNodeIds(new Set());
    setIsPanelOpen(false);
    try {
      const graph = await getDatasetGraph({ id: datasetId });
      setData({ nodes: graph.nodes, links: graph.edges });
    } catch (err) {
      console.error("Failed to load graph", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedDatasetId) loadGraph(selectedDatasetId);
  }, [selectedDatasetId, loadGraph]);

  // Sync displayData when raw data loads
  useEffect(() => {
    setDisplayData(data);
  }, [data]);

  // ── Explore mode ─────────────────────────────────────────────
  const handleExplore = useCallback(() => {
    if (!data) return;
    if (!searchQuery.trim()) {
      setDisplayData(data);
      return;
    }
    const sub = computeSubgraph(data, searchQuery, hops);
    setDisplayData(sub);
    setHighlightedNodeIds(new Set());
    setTimeout(() => graphRef.current?.zoomToFit(400, 40), 100);
  }, [data, searchQuery, hops]);

  // ── Ask mode ──────────────────────────────────────────────────
  const handleAsk = useCallback(async () => {
    if (!searchQuery.trim()) return;
    const dataset = datasets.find((d) => d.id === selectedDatasetId);

    setCurrentQuestion(searchQuery);
    setAnswer("");
    setRelatedNodes([]);
    setIsAnswering(true);
    setIsPanelOpen(true);
    setDisplayData(data); // show full graph while answering

    try {
      const response = await fetch("/v1/search/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: searchQuery,
          searchType: "GRAPH_COMPLETION",
          datasets: [dataset?.name ?? "main_dataset"],
          top_k: 10,
        }),
      });
      const results = await response.json();

      let answerText = "";
      if (Array.isArray(results) && results.length > 0) {
        answerText =
          typeof results[0] === "string"
            ? results[0]
            : results.map((r: { text?: string }) => r.text ?? String(r)).join("\n");
      }
      setAnswer(answerText);

      // Highlight nodes mentioned in the answer
      if (data && answerText) {
        const lowerAnswer = answerText.toLowerCase();
        const matched = data.nodes.filter((n) =>
          lowerAnswer.includes(String(n.label).toLowerCase()),
        );
        setRelatedNodes(matched);
        setHighlightedNodeIds(new Set(matched.map((n) => n.id)));
      }
    } catch (err) {
      console.error("Search failed", err);
      setAnswer("搜索失败，请重试。");
    } finally {
      setIsAnswering(false);
    }
  }, [searchQuery, selectedDatasetId, datasets, data]);

  // ── Form submit ───────────────────────────────────────────────
  const handleSearchSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (searchMode === "explore") handleExplore();
      else handleAsk();
    },
    [searchMode, handleExplore, handleAsk],
  );

  // Clear search
  const clearSearch = useCallback(() => {
    setSearchQuery("");
    setDisplayData(data);
    setHighlightedNodeIds(new Set());
    setIsPanelOpen(false);
  }, [data]);

  // Click related node pill → switch to explore mode on that node
  const focusNode = useCallback(
    (node: GraphNode) => {
      if (!data) return;
      setSearchMode("explore");
      setSearchQuery(String(node.label));
      const sub = computeSubgraph(data, String(node.label), 1);
      setDisplayData(sub);
      setHighlightedNodeIds(new Set());
      setIsPanelOpen(false);
      setTimeout(() => graphRef.current?.zoomToFit(400, 40), 100);
    },
    [data],
  );

  const activeDisplayData = displayData ?? data;

  return (
    <div className="h-full flex flex-col">
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-6 py-3 border-b border-gray-100 bg-white shrink-0">
        {/* Dataset selector */}
        {datasets.length > 0 ? (
          <div className="relative">
            <select
              value={selectedDatasetId}
              onChange={(e) => setSelectedDatasetId(e.target.value)}
              className="appearance-none pl-3 pr-8 h-9 text-sm rounded-lg border border-gray-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-300 cursor-pointer max-w-[180px] truncate"
            >
              {datasets.map((ds) => (
                <option key={ds.id} value={ds.id}>
                  {ds.name}
                </option>
              ))}
            </select>
            <div className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-gray-400">
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </div>
          </div>
        ) : (
          <span className="text-sm text-gray-400">{t("dashboard.graph.noDatasets")}</span>
        )}

        {/* Refresh */}
        <button
          onClick={() => selectedDatasetId && loadGraph(selectedDatasetId)}
          disabled={isLoading || !selectedDatasetId}
          title={t("dashboard.graph.refresh")}
          className="flex items-center justify-center w-9 h-9 text-gray-500 hover:text-indigo-600 border border-gray-200 rounded-lg hover:border-indigo-300 transition-colors disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
        >
          <RefreshIcon spinning={isLoading} />
        </button>

        {/* Search form */}
        <form onSubmit={handleSearchSubmit} className="flex items-center gap-2 flex-1 min-w-0">
          {/* Search input */}
          <div className="relative flex-1 min-w-0">
            <div className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-4.35-4.35M17 11A6 6 0 115 11a6 6 0 0112 0z" />
              </svg>
            </div>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={searchMode === "explore" ? "搜索节点..." : "提问..."}
              className="w-full pl-9 pr-8 h-9 text-sm rounded-lg border border-gray-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-300"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={clearSearch}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>

          {/* Mode toggle */}
          <div className="relative shrink-0">
            <select
              value={searchMode}
              onChange={(e) => setSearchMode(e.target.value as SearchMode)}
              className="appearance-none pl-3 pr-7 h-9 text-sm rounded-lg border border-gray-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-300 cursor-pointer"
            >
              <option value="explore">图谱探索</option>
              <option value="ask">智能问答</option>
            </select>
            <div className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-gray-400">
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </div>
          </div>

          {/* Hop buttons — explore mode only */}
          {searchMode === "explore" && (
            <div className="flex rounded-lg border border-gray-200 overflow-hidden shrink-0">
              {([1, 2] as const).map((h) => (
                <button
                  key={h}
                  type="button"
                  onClick={() => setHops(h)}
                  className={`px-3 h-9 text-xs font-medium transition-colors ${
                    hops === h
                      ? "bg-indigo-600 text-white"
                      : "bg-white text-gray-500 hover:bg-gray-50"
                  }`}
                >
                  {h}跳
                </button>
              ))}
            </div>
          )}

          <button
            type="submit"
            disabled={!searchQuery.trim() || isAnswering}
            className="px-4 h-9 text-sm font-medium bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-lg transition-colors whitespace-nowrap shrink-0"
          >
            {searchMode === "explore" ? "聚焦" : isAnswering ? "搜索中…" : "提问"}
          </button>
        </form>

        {/* Stats */}
        {activeDisplayData && (
          <div className="flex items-center gap-4 text-xs text-gray-400 shrink-0">
            <span>
              {t("dashboard.graph.nodes")}:{" "}
              <span className="font-semibold text-gray-600">{activeDisplayData.nodes.length}</span>
            </span>
            <span>
              {t("dashboard.graph.edges")}:{" "}
              <span className="font-semibold text-gray-600">{activeDisplayData.links.length}</span>
            </span>
          </div>
        )}
      </div>

      {/* Main area: graph + optional answer panel */}
      <div className="flex-1 flex overflow-hidden">
        {/* Graph canvas */}
        <div className="flex-1 relative overflow-hidden bg-gray-50">
          {isLoading && !data && (
            <div className="absolute inset-0 flex items-center justify-center text-gray-400 text-sm">
              <svg className="w-5 h-5 animate-spin mr-2" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              {t("dashboard.graph.loading")}
            </div>
          )}

          <GraphVisualization
            key={selectedDatasetId}
            ref={graphRef as MutableRefObject<GraphVisualizationAPI>}
            data={activeDisplayData as any}
            graphControls={graphControls as MutableRefObject<GraphControlsAPI>}
            highlightedNodeIds={highlightedNodeIds}
            className="w-full h-full"
          />

          {/* Legend overlay */}
          {!!activeDisplayData?.nodes.length && (
            <div className="absolute top-3 right-3 z-10 bg-white/90 backdrop-blur-sm rounded-xl shadow-sm border border-gray-100 p-4 w-48">
              <GraphLegend data={activeDisplayData.nodes as any} />
            </div>
          )}

          {/* Subgraph info badge */}
          {searchQuery && searchMode === "explore" && displayData && data && displayData.nodes.length < data.nodes.length && (
            <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-10 bg-white/90 backdrop-blur-sm rounded-full shadow-lg px-5 py-2 text-sm text-gray-600 flex items-center gap-3">
              <span>显示 {displayData.nodes.length} / {data.nodes.length} 个节点</span>
              <button
                onClick={clearSearch}
                className="text-indigo-600 hover:text-indigo-800 text-xs font-medium"
              >
                查看全图
              </button>
            </div>
          )}
        </div>

        {/* Answer panel */}
        {isPanelOpen && (
          <div className="w-80 shrink-0 border-l border-gray-100 bg-white flex flex-col overflow-hidden">
            {/* Panel header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100 shrink-0">
              <span className="text-sm font-medium text-gray-700">智能问答</span>
              <button
                onClick={() => {
                  setIsPanelOpen(false);
                  setHighlightedNodeIds(new Set());
                }}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-4">
              {/* Question */}
              <div className="text-sm text-gray-500 bg-gray-50 rounded-lg px-3 py-2 leading-relaxed">
                Q: {currentQuestion}
              </div>

              {/* Loading */}
              {isAnswering && (
                <div className="flex items-center gap-2 text-sm text-gray-400">
                  <svg className="w-4 h-4 animate-spin shrink-0" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  正在查询知识图谱…
                </div>
              )}

              {/* Answer */}
              {answer && (
                <div className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
                  {answer}
                </div>
              )}

              {/* Related nodes */}
              {relatedNodes.length > 0 && (
                <div>
                  <p className="text-xs text-gray-400 mb-2">📍 关联节点（点击聚焦）</p>
                  <div className="flex flex-wrap gap-1.5">
                    {relatedNodes.map((node) => (
                      <button
                        key={node.id}
                        onClick={() => focusNode(node)}
                        className="px-2.5 py-1 text-xs rounded-full bg-indigo-50 text-indigo-700 hover:bg-indigo-100 transition-colors border border-indigo-100"
                      >
                        {node.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
