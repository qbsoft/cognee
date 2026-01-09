"use client";

import React, { FormEvent, MutableRefObject, useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import apiFetch from "@/utils/fetch";
import { CTAButton, GhostButton, Input } from "@/ui/elements";
import { LoadingIndicator } from "@/ui/App";
import GraphVisualization, { GraphVisualizationAPI } from "../../../(graph)/GraphVisualization";
import type { GraphControlsAPI } from "../../../(graph)/GraphControls";
import type { GraphData, LinkObject, NodeObject } from "react-force-graph-2d";

// 图标组件
const SearchIcon = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
  </svg>
);

const FileIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
  </svg>
);

const GraphIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
  </svg>
);

const BackIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
  </svg>
);

const ExpandIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
  </svg>
);

const CollapseIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
  </svg>
);

const ChevronLeftIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
  </svg>
);

const ChevronRightIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
  </svg>
);

interface DatasetSearchPageProps {
  params: Promise<{
    datasetId: string;
  }>;
}

interface DatasetSummary {
  id: string;
  name: string;
}

interface DatasetDataItem {
  id: string;
  name: string;
  created_at: string;
  updated_at?: string | null;
  extension: string;
  mime_type: string;
  raw_data_location: string;
  dataset_id: string;
}

// Server Component - 处理异步参数
export default function DatasetSearchPage({ params }: DatasetSearchPageProps) {
  // 使用 React.use() 来解析 Promise (Next.js 15+)
  const unwrappedParams = React.use(params);
  return <DatasetSearchPageClient datasetId={unwrappedParams.datasetId} />;
}

// Client Component - 包含所有客户端逻辑
function DatasetSearchPageClient({ datasetId }: { datasetId: string }) {
  const router = useRouter();

  const [dataset, setDataset] = useState<DatasetSummary | null>(null);
  const [dataItems, setDataItems] = useState<DatasetDataItem[]>([]);
  const [dataLoading, setDataLoading] = useState(false);
  const [selectedDataId, setSelectedDataId] = useState<string | null>(null);
  const [currentFileIndex, setCurrentFileIndex] = useState(0);
  const [fileContent, setFileContent] = useState<string>("");
  const [fileContentLoading, setFileContentLoading] = useState(false);
  const [fileContentError, setFileContentError] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [searchResult, setSearchResult] = useState<any>(null);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  const [graphData, setGraphData] = useState<GraphData<NodeObject, LinkObject> | undefined>();
  const [graphLoading, setGraphLoading] = useState(false);
  const [graphError, setGraphError] = useState<string | null>(null);
  const [graphExpanded, setGraphExpanded] = useState(false);
  
  // 搜索结果相关的图谱数据
  const [searchGraphData, setSearchGraphData] = useState<GraphData<NodeObject, LinkObject> | undefined>();
  const [showSearchGraph, setShowSearchGraph] = useState(false);
  const [fullGraphData, setFullGraphData] = useState<GraphData<NodeObject, LinkObject> | undefined>();

  const graphRef = useRef<GraphVisualizationAPI>();
  const graphControlsRef = useRef<GraphControlsAPI>();

  const loadDatasetInfo = useCallback(async () => {
    try {
      const response = await apiFetch("/v1/datasets", {
        headers: { "Content-Type": "application/json" },
      });
      const datasets: DatasetSummary[] = await response.json();
      const current = datasets.find((d) => d.id === datasetId);
      if (current) {
        setDataset(current);
      } else {
        setDataset({ id: datasetId, name: datasetId });
      }
    } catch (error) {
      setDataset({ id: datasetId, name: datasetId });
    }
  }, [datasetId]);

  const loadDatasetData = useCallback(async () => {
    setDataLoading(true);
    setFileContent("");
    setFileContentError(null);
    setSelectedDataId(null);
    try {
      const response = await apiFetch(`/v1/datasets/${datasetId}/data`, {
        headers: { "Content-Type": "application/json" },
      });
      const data: DatasetDataItem[] = await response.json();
      setDataItems(data);
    } catch (error: any) {
      setFileContentError(error?.message || "加载数据集文件列表失败");
    } finally {
      setDataLoading(false);
    }
  }, [datasetId]);

  // 将图谱数据转换为前端格式
  const normalizeGraphData = useCallback((graph: { nodes?: any[], edges?: any[] }) => {
    return {
      nodes: (graph.nodes || []).map((node: any) => {
        // 处理空节点名称
        let label = node.label || node.name || '';
        
        // 如果 label 为空，尝试使用其他字段
        if (!label || label.trim() === '') {
          // 尝试使用 text 字段的前几个词
          const text = node.text || node.attributes?.text;
          if (text && text.trim()) {
            const textStr = text.trim();
            const firstLine = textStr.split('\n')[0];
            label = firstLine.length > 30 ? firstLine.substring(0, 30) + '...' : firstLine;
          }
          // 尝试使用 description
          else {
            const desc = node.description || node.attributes?.description;
            if (desc && desc.trim()) {
              const descStr = desc.trim();
              label = descStr.length > 30 ? descStr.substring(0, 30) + '...' : descStr;
            }
          }
          
          // 如果还是为空，使用类型和ID
          if (!label || label.trim() === '') {
            const nodeType = node.type || 'unknown';
            const typeMap: Record<string, string> = {
              'DocumentChunk': '文档片段',
              'TextDocument': '文档',
              'Entity': '实体',
              'EntityType': '实体类型',
              'TextSummary': '摘要',
            };
            const translatedType = typeMap[nodeType] || nodeType;
            label = `${translatedType}_${node.id?.substring(0, 8) || 'unknown'}`;
          }
        }
        
        return {
          ...node,
          label: label,
        };
      }),
      links: (graph.edges || []).map((edge: any) => ({
        source: edge.source,
        target: edge.target,
        label: edge.label || '关联',
      })),
    } as GraphData<NodeObject, LinkObject>;
  }, []);

  const loadGraph = useCallback(async () => {
    setGraphLoading(true);
    setGraphError(null);
    try {
      const response = await apiFetch(`/v1/datasets/${datasetId}/graph`, {
        headers: { "Content-Type": "application/json" },
      });
      const graph = await response.json();
      
      const normalized = normalizeGraphData(graph);
      setGraphData(normalized);
      setFullGraphData(normalized); // 保存完整图谱数据
    } catch (error: any) {
      setGraphError(error?.message || "加载图关系数据失败");
    } finally {
      setGraphLoading(false);
    }
  }, [datasetId, normalizeGraphData]);

  useEffect(() => {
    loadDatasetInfo();
    loadDatasetData();
    loadGraph();
  }, [loadDatasetInfo, loadDatasetData, loadGraph]);

  // 自动选择第一个文件
  useEffect(() => {
    if (dataItems.length > 0 && !selectedDataId) {
      handleSelectData(dataItems[0], 0);
      setCurrentFileIndex(0);
    }
  }, [dataItems, selectedDataId]);

  const handleSelectData = useCallback(async (item: DatasetDataItem, index?: number) => {
    setSelectedDataId(item.id);
    if (index !== undefined) {
      setCurrentFileIndex(index);
    }
    setFileContent("");
    setFileContentError(null);
    setFileContentLoading(true);

    try {
      const response = await apiFetch(`/v1/datasets/${datasetId}/data/${item.id}/raw`);
      const contentType = response.headers.get("Content-Type") || "";

      if (contentType.startsWith("text/") || contentType.includes("json") || contentType.includes("xml")) {
        const text = await response.text();
        setFileContent(text);
      } else {
        setFileContent("该文件为非文本类型，当前暂不支持在线预览。");
      }
    } catch (error: any) {
      console.error("加载文件内容失败:", error);
      setFileContentError(error?.message || "加载文件内容失败");
    } finally {
      setFileContentLoading(false);
    }
  }, [datasetId]);

  const handlePrevFile = () => {
    if (dataItems.length === 0) return;
    const newIndex = currentFileIndex > 0 ? currentFileIndex - 1 : dataItems.length - 1;
    setCurrentFileIndex(newIndex);
    handleSelectData(dataItems[newIndex], newIndex);
  };

  const handleNextFile = () => {
    if (dataItems.length === 0) return;
    const newIndex = currentFileIndex < dataItems.length - 1 ? currentFileIndex + 1 : 0;
    setCurrentFileIndex(newIndex);
    handleSelectData(dataItems[newIndex], newIndex);
  };

  const handleSearch = useCallback(async (event?: FormEvent) => {
    if (event) event.preventDefault();
    if (!searchQuery.trim()) return;

    setSearching(true);
    setSearchError(null);

    try {
      const response = await apiFetch("/v1/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          search_type: "GRAPH_COMPLETION",
          dataset_ids: [datasetId],
          query: searchQuery,
          use_combined_context: true,
          top_k: 30,  // 增加检索数量以提高相关性
        }),
      });

      const data = await response.json();
      console.log('=== 搜索结果数据结构 ===');
      console.log('完整数据:', data);
      console.log('result类型:', typeof data.result, 'result值:', data.result);
      console.log('context类型:', typeof data.context, 'context是数组?', Array.isArray(data.context));
      console.log('graphs字段:', data.graphs);
      
      setSearchResult(data);
      
      // 根据搜索结果更新图谱
      if (data.graphs && typeof data.graphs === 'object') {
        // graphs 是一个对象，键是数据集名称，值是图谱数据
        const graphEntries = Object.entries(data.graphs);
        if (graphEntries.length > 0) {
          // 合并所有数据集的图谱
          const allNodesMap = new Map<string, any>();
          const allEdgesSet = new Set<string>();
          const allEdges: any[] = [];
          
          graphEntries.forEach(([datasetName, graph]: [string, any]) => {
            // 合并节点
            if (graph.nodes && Array.isArray(graph.nodes)) {
              graph.nodes.forEach((node: any) => {
                if (node.id) {
                  allNodesMap.set(node.id, node);
                }
              });
            }
            
            // 合并边
            if (graph.edges && Array.isArray(graph.edges)) {
              graph.edges.forEach((edge: any) => {
                const edgeKey = `${edge.source}_${edge.target}_${edge.label || ''}`;
                if (!allEdgesSet.has(edgeKey)) {
                  allEdgesSet.add(edgeKey);
                  allEdges.push(edge);
                }
              });
            }
          });
          
          // 转换为前端格式
          const searchGraph = normalizeGraphData({
            nodes: Array.from(allNodesMap.values()),
            edges: allEdges,
          });
          
          setSearchGraphData(searchGraph);
          setShowSearchGraph(true); // 自动切换到搜索结果图谱
          setGraphData(searchGraph); // 更新显示的图谱
          
          console.log('已根据搜索结果更新图谱，节点数:', searchGraph.nodes.length, '边数:', searchGraph.links.length);
        } else {
          console.log('graphs对象为空，保持显示完整数据集图谱');
          setShowSearchGraph(false);
        }
      } else {
        console.log('搜索结果中没有图谱数据，保持显示完整数据集图谱');
        setShowSearchGraph(false);
        // 恢复显示完整图谱
        if (fullGraphData) {
          setGraphData(fullGraphData);
        }
      }
    } catch (error: any) {
      setSearchError(error?.message || "检索失败");
    } finally {
      setSearching(false);
    }
  }, [datasetId, searchQuery]);

  // 处理引用点击 - 打开左侧文件并滚动到精确位置
  const handleCitationClick = async (index: number) => {
    console.log('[Citation] === 开始处理引用点击 ===');
    console.log('[Citation] 点击索引:', index);
    console.log('[Citation] searchResult:', searchResult);
    console.log('[Citation] dataItems长度:', dataItems.length);
    
    // 将context转换为数组格式
    let contextArray: any[] = [];
    if (searchResult?.context) {
      if (Array.isArray(searchResult.context)) {
        contextArray = searchResult.context;
        console.log('[Citation] context是数组');
      } else if (typeof searchResult.context === 'object') {
        // context是对象 {dataset_id: [contexts]}
        contextArray = Object.values(searchResult.context).flat();
        console.log('[Citation] context是对象，转换后数组长度:', contextArray.length);
      }
    }
    
    console.log('[Citation] contextArray:', contextArray);
      
    // 获取对应的context项
    if (contextArray[index]) {
      const ctx = contextArray[index];
      console.log('[Citation] 选中的context:', ctx);
      console.log('[Citation] source_file_path:', ctx.source_file_path);
      console.log('[Citation] start_line:', ctx.start_line);
      console.log('[Citation] end_line:', ctx.end_line);
        
      // 尝试打开对应文件
      let fileToOpen = null;
      let fileIndex = -1;
        
      // 优先使用source_file_path查找
      if (ctx.source_file_path) {
        console.log('[Citation] 尝试匹配文件:', ctx.source_file_path);
        console.log('[Citation] 可用文件列表:', dataItems.map(item => item.name));
        
        fileIndex = dataItems.findIndex(item => 
          item.name.includes(ctx.source_file_path) || 
          ctx.source_file_path.includes(item.name)
        );
        
        console.log('[Citation] 匹配到的文件索引:', fileIndex);
      }
        
      // 如果找不到，尝试从text中提取文件名
      if (fileIndex === -1 && ctx.text) {
        const fileMatch = ctx.text.match(/([\w\-\u4e00-\u9fa5]+\.(txt|pdf|docx|md|doc|csv|json|xml))/);
        if (fileMatch) {
          const fileName = fileMatch[1];
          fileIndex = dataItems.findIndex(item => 
            item.name.includes(fileName) || fileName.includes(item.name)
          );
        }
      }
        
      if (fileIndex !== -1) {
        fileToOpen = dataItems[fileIndex];
        console.log('[Citation] 准备打开文件:', fileToOpen.name);
        
        await handleSelectData(fileToOpen, fileIndex);
        console.log('[Citation] 文件打开完成，等待300ms后滚动');
          
        // 等待文件加载完成后滚动到指定行
        setTimeout(() => {
          console.log('[Citation] 开始执行滚动逻辑');
          console.log('[Citation] ctx.start_line:', ctx.start_line, 'ctx.end_line:', ctx.end_line);
          
          if (ctx.start_line && ctx.end_line) {
            // 查找文件内容容器（实际是 overflow-auto 的 div）
            const fileContainerSelectors = [
              '.overflow-auto.p-4',  // 实际的容器
              'pre',  // pre标签
            ];
            
            let scrollContainer = null;
            let contentElement = null;
            
            // 尝试找到滚动容器和内容元素
            for (const selector of fileContainerSelectors) {
              const elements = document.querySelectorAll(selector);
              if (elements.length > 0) {
                // 找到包含文件内容的元素（在左侧栏）
                const leftPanel = document.querySelector('.col-span-12.lg\\:col-span-7');
                if (leftPanel) {
                  for (const el of Array.from(elements)) {
                    if (leftPanel.contains(el as Node)) {
                      if (selector === '.overflow-auto.p-4') {
                        scrollContainer = el as HTMLElement;
                        contentElement = el.querySelector('pre');
                      } else if (selector === 'pre') {
                        contentElement = el as HTMLElement;
                        scrollContainer = el.parentElement;
                      }
                      break;
                    }
                  }
                }
                if (scrollContainer) break;
              }
            }
            
            console.log('[Citation] scrollContainer:', scrollContainer);
            console.log('[Citation] contentElement:', contentElement);
            
            if (scrollContainer && contentElement) {
              // 获取文件内容
              const fileText = contentElement.textContent || '';
              
              console.log('[Citation] 文件总长度:', fileText.length);
              console.log('[Citation] context.start_char:', ctx.start_char, 'context.end_char:', ctx.end_char);
              console.log('[Citation] context.text前100字符:', ctx.text?.substring(0, 100));
              
              // 优先使用 start_char/end_char 进行精确定位
              if (ctx.start_char !== null && ctx.start_char !== undefined && 
                  ctx.end_char !== null && ctx.end_char !== undefined) {
                console.log('[Citation] 使用start_char/end_char进行精确定位');
                
                // 使用Range API精确定位
                const range = document.createRange();
                const textNode = contentElement.firstChild;
                
                if (textNode && textNode.nodeType === Node.TEXT_NODE) {
                  try {
                    const start = Math.max(0, Math.min(ctx.start_char, fileText.length));
                    const end = Math.max(start, Math.min(ctx.end_char, fileText.length));
                    
                    console.log('[Citation] Range范围:', start, '-', end);
                    
                    range.setStart(textNode, start);
                    range.setEnd(textNode, end);
                    
                    // 计算位置
                    const rect = range.getBoundingClientRect();
                    const containerRect = scrollContainer.getBoundingClientRect();
                    const relativeTop = rect.top - containerRect.top + scrollContainer.scrollTop;
                    
                    console.log('[Citation] 精确滚动位置:', relativeTop);
                    
                    // 滚动到目标位置（居中显示）
                    const offset = scrollContainer.clientHeight / 3; // 显示在上部1/3处
                    scrollContainer.scrollTo({
                      top: Math.max(0, relativeTop - offset),
                      behavior: 'smooth'
                    });
                    
                    console.log('[Citation] 精确滚动已执行 (start_char/end_char)');
                    
                    // 添加精确的文本高亮效果
                    // 创建一个临时的高亮span元素
                    const highlightId = 'citation-highlight-' + Date.now();
                    const fragment = range.extractContents();
                    const highlightSpan = document.createElement('span');
                    highlightSpan.id = highlightId;
                    highlightSpan.style.backgroundColor = '#fef3c7'; // 黄色高亮
                    highlightSpan.style.transition = 'background-color 0.3s ease';
                    highlightSpan.appendChild(fragment);
                    range.insertNode(highlightSpan);
                    
                    // 20秒后移除高亮
                    setTimeout(() => {
                      const highlight = document.getElementById(highlightId);
                      if (highlight && highlight.parentNode) {
                        // 将高亮文本还原为普通文本
                        while (highlight.firstChild) {
                          highlight.parentNode.insertBefore(highlight.firstChild, highlight);
                        }
                        highlight.parentNode.removeChild(highlight);
                      }
                    }, 20000);
                    
                  } catch (e) {
                    console.log('[Citation] Range API错误:', e);
                    // 降级处理：使用start_line
                    const lineHeight = 20;
                    const targetScrollTop = (ctx.start_line - 1) * lineHeight;
                    scrollContainer.scrollTo({
                      top: targetScrollTop,
                      behavior: 'smooth'
                    });
                  }
                }
              } 
              // 如果没有start_char/end_char，尝试使用context.text进行文本匹配
              else if (ctx.text && ctx.text.length > 50) {
                console.log('[Citation] start_char/end_char不可用，使用context.text匹配');
                // 取前100个字符作为搜索关键词
                const searchText = ctx.text.substring(0, 100).trim();
                const textIndex = fileText.indexOf(searchText);
                
                console.log('[Citation] 搜索关键词:', searchText.substring(0, 50) + '...');
                console.log('[Citation] 找到的位置索引:', textIndex);
                
                if (textIndex !== -1) {
                  // 找到了！使用Range API精确定位
                  const range = document.createRange();
                  const textNode = contentElement.firstChild;
                  
                  if (textNode && textNode.nodeType === Node.TEXT_NODE) {
                    try {
                      range.setStart(textNode, textIndex);
                      range.setEnd(textNode, Math.min(textIndex + 100, fileText.length));
                      
                      const rect = range.getBoundingClientRect();
                      const containerRect = scrollContainer.getBoundingClientRect();
                      const relativeTop = rect.top - containerRect.top + scrollContainer.scrollTop;
                      
                      console.log('[Citation] 精确滚动位置:', relativeTop);
                      
                      const offset = scrollContainer.clientHeight / 3;
                      scrollContainer.scrollTo({
                        top: Math.max(0, relativeTop - offset),
                        behavior: 'smooth'
                      });
                      
                      console.log('[Citation] 精确滚动已执行 (text匹配)');
                      
                      // 添加精确的文本高亮效果
                      const highlightId = 'citation-highlight-' + Date.now();
                      const fragment = range.extractContents();
                      const highlightSpan = document.createElement('span');
                      highlightSpan.id = highlightId;
                      highlightSpan.style.backgroundColor = '#fef3c7';
                      highlightSpan.style.transition = 'background-color 0.3s ease';
                      highlightSpan.appendChild(fragment);
                      range.insertNode(highlightSpan);
                      
                      setTimeout(() => {
                        const highlight = document.getElementById(highlightId);
                        if (highlight && highlight.parentNode) {
                          while (highlight.firstChild) {
                            highlight.parentNode.insertBefore(highlight.firstChild, highlight);
                          }
                          highlight.parentNode.removeChild(highlight);
                        }
                      }, 20000);
                      
                    } catch (e) {
                      console.log('[Citation] Range API错误:', e);
                      // 降级为start_line
                      if (ctx.start_line) {
                        const lineHeight = 20;
                        const targetScrollTop = (ctx.start_line - 1) * lineHeight;
                        scrollContainer.scrollTo({
                          top: targetScrollTop,
                          behavior: 'smooth'
                        });
                      }
                    }
                  }
                } else {
                  console.log('[Citation] 未找到匹配文本，使用start_line估算');
                  // 降级方案：使用start_line
                  if (ctx.start_line) {
                    const lineHeight = 20;
                    const targetScrollTop = (ctx.start_line - 1) * lineHeight;
                    scrollContainer.scrollTo({
                      top: targetScrollTop,
                      behavior: 'smooth'
                    });
                  }
                }
              } 
              // 最后降级：只有start_line
              else if (ctx.start_line) {
                console.log('[Citation] 只有start_line可用，使用行号估算');
                const lineHeight = 20;
                const targetScrollTop = (ctx.start_line - 1) * lineHeight;
                scrollContainer.scrollTo({
                  top: targetScrollTop,
                  behavior: 'smooth'
                });
              } else {
                console.log('[Citation] 没有任何位置信息可用');
              }
            } else {
              console.log('[Citation] 错误: 没有找到滚动容器或内容元素');
            }
          } else {
            console.log('[Citation] 错误: 缺少start_line或end_line');
          }
        }, 500); // 增加等待时间到500ms
      } else {
        console.log('[Citation] 错误: 没有匹配到文件');
      }
    } else {
      console.log('[Citation] 错误: contextArray[' + index + '] 不存在');
    }
  };

  const renderSearchResult = () => {
    if (!searchResult) {
      return (
        <div className="flex flex-col items-center justify-center h-full py-12 text-center">
          <div className="w-16 h-16 rounded-full bg-indigo-50 flex items-center justify-center mb-4">
            <SearchIcon />
          </div>
          <p className="text-gray-500 text-sm">输入问题开始检索</p>
          <p className="text-gray-400 text-xs mt-1">基于知识图谱进行语义检索与问答</p>
        </div>
      );
    }

    if (Array.isArray(searchResult)) {
      if (searchResult.length === 0) {
        return (
          <div className="flex flex-col items-center justify-center h-full py-8">
            <p className="text-gray-500 text-sm">未找到匹配结果</p>
            <p className="text-gray-400 text-xs mt-1">请尝试使用不同的关键词</p>
          </div>
        );
      }

      return (
        <div className="space-y-3 overflow-y-auto">
          {searchResult.map((item, index) => (
            <div key={index} className="border border-gray-200 rounded-lg p-3 bg-white hover:shadow-sm transition-shadow">
              {item.dataset_name && (
                <div className="text-xs text-indigo-600 font-medium mb-2">
                  📁 {item.dataset_name}
                </div>
              )}
              <pre className="whitespace-pre-wrap break-words text-sm text-gray-700">
                {JSON.stringify(item.search_result ?? item, null, 2)}
              </pre>
            </div>
          ))}
        </div>
      );
    }

    return (
      <div className="space-y-4 overflow-y-auto">
        {searchResult.result && (
          <div className="bg-gradient-to-r from-indigo-50 to-purple-50 rounded-lg p-4 border border-indigo-100">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-lg">💡</span>
              <span className="font-semibold text-gray-800">回答</span>
            </div>
            <div className="text-gray-700 leading-relaxed">
              {(() => {
                const resultText = typeof searchResult.result === "string"
                  ? searchResult.result
                  : JSON.stringify(searchResult.result, null, 2);
                
                // 处理context，无论是数组还是对象
                let contextArray: any[] = [];
                if (searchResult.context) {
                  if (Array.isArray(searchResult.context)) {
                    contextArray = searchResult.context;
                  } else if (typeof searchResult.context === 'object') {
                    // context是对象 {dataset_id: [contexts]}, 将所有contexts合并
                    contextArray = Object.values(searchResult.context).flat();
                  }
                }
                
                // 过滤出有位置信息的DocumentChunk节点
                const citableContexts = contextArray.filter((ctx: any) => 
                  ctx.node_type === 'DocumentChunk' && 
                  ctx.source_file_path && 
                  ctx.start_line != null
                );
                
                // 如果有可引用的context,在文本中智能嵌入上标引用
                if (citableContexts.length > 0) {
                  // 尝试智能匹配：在回答文本中找到与context相关的位置
                  const sentences = resultText.split(/([。！？\n])/); // 按句子分割
                  const annotatedParts: React.ReactNode[] = [];
                  let usedCitations = new Set<number>();
                  
                  sentences.forEach((sentence: string, sentIdx: number) => {
                    if (sentence.match(/[。！？\n]/)) {
                      // 这是标点符号,直接添加
                      annotatedParts.push(sentence);
                      return;
                    }
                    
                    if (!sentence.trim()) {
                      annotatedParts.push(sentence);
                      return;
                    }
                    
                    // 对每个句子，找出最相关的引用
                    const relevantCitations: number[] = [];
                    citableContexts.forEach((ctx: any, idx: number) => {
                      if (usedCitations.has(idx)) return;
                      
                      // 检查context.text中是否包含这个句子的关键词
                      if (ctx.text && ctx.text.length > 10) {
                        const keywords = sentence.match(/[\u4e00-\u9fa5]{2,}/g) || [];
                        const matchCount = keywords.filter((kw: string) => ctx.text.includes(kw)).length;
                        
                        if (matchCount > 0) {
                          relevantCitations.push(idx);
                        }
                      }
                    });
                    
                    // 添加句子文本
                    annotatedParts.push(
                      <span key={`sent-${sentIdx}`}>{sentence}</span>
                    );
                    
                    // 添加上标引用
                    if (relevantCitations.length > 0) {
                      relevantCitations.forEach(citIdx => {
                        usedCitations.add(citIdx);
                        const originalIndex = contextArray.findIndex((c: any) => c === citableContexts[citIdx]);
                        annotatedParts.push(
                          <sup key={`cite-${sentIdx}-${citIdx}`}>
                            <button
                              onClick={() => handleCitationClick(originalIndex)}
                              className="text-indigo-600 hover:text-indigo-800 font-medium cursor-pointer mx-0.5"
                              title="点击查看原文出处"
                            >
                              [{citIdx + 1}]
                            </button>
                          </sup>
                        );
                      });
                    }
                  });
                  
                  // 如果还有未使用的引用，在文本末尾统一添加
                  const unusedCitations = citableContexts
                    .map((_, idx) => idx)
                    .filter(idx => !usedCitations.has(idx));
                  
                  return (
                    <div>
                      <div className="whitespace-pre-wrap leading-relaxed">
                        {annotatedParts}
                        {unusedCitations.length > 0 && (
                          <span>
                            {unusedCitations.map(citIdx => {
                              const originalIndex = contextArray.findIndex((c: any) => c === citableContexts[citIdx]);
                              return (
                                <sup key={`unused-${citIdx}`}>
                                  <button
                                    onClick={() => handleCitationClick(originalIndex)}
                                    className="text-indigo-600 hover:text-indigo-800 font-medium cursor-pointer mx-0.5"
                                    title="点击查看原文出处"
                                  >
                                    [{citIdx + 1}]
                                  </button>
                                </sup>
                              );
                            })}
                          </span>
                        )}
                      </div>
                      
                      {/* 引用列表（鼠标悬停提示）*/}
                      <div className="mt-3 pt-3 border-t border-gray-200 text-xs text-gray-600">
                        <div className="font-medium mb-1.5">引用来源：</div>
                        <div className="space-y-1">
                          {citableContexts.map((ctx: any, idx: number) => {
                            const fileName = ctx.source_file_path || '未知文件';
                            const lineInfo = ctx.start_line && ctx.end_line 
                              ? `第${ctx.start_line}-${ctx.end_line}行`
                              : ctx.start_line 
                                ? `第${ctx.start_line}行`
                                : '';
                            
                            return (
                              <div key={idx} className="text-gray-500">
                                [{idx + 1}] {fileName} {lineInfo}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    </div>
                  );
                }
                return <div className="whitespace-pre-wrap">{resultText}</div>;
              })()}
            </div>
          </div>
        )}
      </div>
    );
  };

  // 图谱全屏弹窗
  const renderGraphModal = () => {
    if (!graphExpanded) return null;
    
    return (
      <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-2xl w-full max-w-6xl h-[85vh] flex flex-col overflow-hidden">
          <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-gradient-to-r from-indigo-50 to-purple-50">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-indigo-600 flex items-center justify-center text-white">
                <GraphIcon />
              </div>
              <div>
                <h3 className="font-semibold text-gray-900">知识图谱</h3>
                <p className="text-xs text-gray-500">数据集：{dataset?.name}</p>
              </div>
            </div>
            <button
              onClick={() => setGraphExpanded(false)}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <CollapseIcon />
            </button>
          </div>
          <div className="flex-1 bg-gray-50 flex flex-col">
            {/* 切换按钮 */}
            {searchGraphData && fullGraphData && (
              <div className="px-4 py-2 border-b border-gray-200 bg-white flex items-center gap-2">
                <button
                  onClick={() => {
                    setShowSearchGraph(!showSearchGraph);
                    setGraphData(showSearchGraph ? fullGraphData : searchGraphData);
                  }}
                  className={`px-3 py-1.5 text-xs rounded-lg transition-colors ${
                    showSearchGraph 
                      ? 'bg-indigo-600 text-white' 
                      : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                  }`}
                >
                  {showSearchGraph ? '显示完整图谱' : '显示搜索结果图谱'}
                </button>
                {showSearchGraph && searchGraphData && (
                  <span className="text-xs text-gray-500">
                    ({searchGraphData.nodes.length} 个节点, {searchGraphData.links.length} 条边)
                  </span>
                )}
                {!showSearchGraph && fullGraphData && (
                  <span className="text-xs text-gray-500">
                    ({fullGraphData.nodes.length} 个节点, {fullGraphData.links.length} 条边)
                  </span>
                )}
              </div>
            )}
            <div className="flex-1">
              {graphData ? (
                <GraphVisualization
                  key={`expanded-${showSearchGraph ? 'search' : 'full'}-${graphData.nodes?.length}`}
                  ref={graphRef as MutableRefObject<GraphVisualizationAPI>}
                  data={graphData as unknown as GraphData<NodeObject, LinkObject>}
                  graphControls={graphControlsRef as MutableRefObject<GraphControlsAPI>}
                  className="w-full h-full"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-gray-400">
                  暂无图数据
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-indigo-50/30 to-purple-50/30">
      {renderGraphModal()}
      
      {/* 顶部导航栏 */}
      <div className="sticky top-0 z-40 bg-white/80 backdrop-blur-md border-b border-gray-200/50">
        <div className="max-w-[1800px] mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button
                onClick={() => router.push("/dashboard")}
                className="flex items-center gap-2 px-3 py-2 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <BackIcon />
                <span>返回</span>
              </button>
              <div className="h-6 w-px bg-gray-200" />
              <div>
                <div className="text-xs text-indigo-600 font-medium">数据集检索</div>
                <div className="text-lg font-bold text-gray-900">
                  {dataset?.name || "加载中..."}
                </div>
              </div>
            </div>
            <div className="hidden lg:flex items-center gap-2 text-xs text-gray-500">
              <span className="px-2 py-1 bg-green-100 text-green-700 rounded">✓ add</span>
              <span>→</span>
              <span className="px-2 py-1 bg-green-100 text-green-700 rounded">✓ cognify</span>
              <span>→</span>
              <span className="px-2 py-1 bg-green-100 text-green-700 rounded">✓ memify</span>
              <span>→</span>
              <span className="px-2 py-1 bg-indigo-600 text-white rounded font-medium">search</span>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-[1800px] mx-auto px-6 py-6">
        {/* 搜索框区域 - 突出展示 */}
        <div className="mb-6">
          <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
            <form onSubmit={handleSearch}>
              <div className="flex items-center gap-4">
                <div className="flex-1 relative">
                  <div className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400">
                    <SearchIcon />
                  </div>
                  <input
                    type="text"
                    placeholder="输入你的问题，例如：文档的核心结论是什么？主要观点有哪些？"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full pl-12 pr-4 py-4 text-base border-2 border-gray-200 rounded-xl focus:border-indigo-500 focus:ring-4 focus:ring-indigo-100 outline-none transition-all"
                  />
                </div>
                <CTAButton 
                  type="submit" 
                  disabled={searching || !searchQuery.trim()}
                  className="px-8 py-4 text-base"
                >
                  {searching ? (
                    <span className="flex items-center gap-2">
                      <LoadingIndicator />
                      检索中...
                    </span>
                  ) : (
                    "开始检索"
                  )}
                </CTAButton>
              </div>
              {searchError && (
                <div className="mt-3 text-sm text-red-600 flex items-center gap-2">
                  <span>⚠️</span>
                  {searchError}
                </div>
              )}
            </form>
          </div>
        </div>

        {/* 主内容区域 - 两栏布局 */}
        <div className="grid grid-cols-12 gap-6" style={{ height: 'calc(100vh - 280px)' }}>
          
          {/* 左侧：文件内容预览 - 58% */}
          <div className="col-span-12 lg:col-span-7 bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden flex flex-col">
            {/* 文件列表横条 */}
            <div className="px-4 py-3 border-b border-gray-100 bg-gradient-to-r from-gray-50 to-white">
              <div className="flex items-center gap-3">
                <button
                  onClick={handlePrevFile}
                  disabled={dataItems.length === 0}
                  className="p-1.5 hover:bg-gray-200 rounded-lg transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                  title="上一个文件"
                >
                  <ChevronLeftIcon />
                </button>
                
                <div className="flex-1 min-w-0 group relative">
                  {dataItems.length > 0 ? (
                    <>
                      <div className="flex items-center gap-2">
                        <FileIcon />
                        <span className="font-semibold text-gray-800 truncate">
                          {dataItems[currentFileIndex]?.name || '未选择文件'}
                        </span>
                        <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full flex-shrink-0">
                          {currentFileIndex + 1} / {dataItems.length}
                        </span>
                      </div>
                      {/* 鼠标悬停显示完整文件名 */}
                      <div className="absolute left-0 top-full mt-1 z-10 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                        <div className="bg-gray-900 text-white text-xs px-3 py-2 rounded-lg shadow-lg max-w-md">
                          {dataItems[currentFileIndex]?.name}
                        </div>
                      </div>
                    </>
                  ) : (
                    <div className="flex items-center gap-2 text-gray-400">
                      <FileIcon />
                      <span className="text-sm">暂无文件</span>
                    </div>
                  )}
                </div>
                
                <button
                  onClick={handleNextFile}
                  disabled={dataItems.length === 0}
                  className="p-1.5 hover:bg-gray-200 rounded-lg transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                  title="下一个文件"
                >
                  <ChevronRightIcon />
                </button>

                {fileContentLoading && (
                  <span className="flex items-center gap-1 text-xs text-gray-500">
                    <LoadingIndicator />
                    加载中...
                  </span>
                )}
              </div>
            </div>
            
            {/* 文件内容区域 */}
            <div className="flex-1 overflow-auto p-4 bg-gray-50/50">
              {fileContentError && (
                <div className="bg-red-50 text-red-600 px-4 py-3 rounded-lg text-sm">
                  {fileContentError}
                </div>
              )}
              {!fileContent && !fileContentError && !fileContentLoading && (
                <div className="flex flex-col items-center justify-center h-full text-center">
                  <div className="w-16 h-16 rounded-full bg-gray-100 flex items-center justify-center mb-4">
                    <FileIcon />
                  </div>
                  <p className="text-gray-500 text-sm">点击左右箭头浏览文件</p>
                </div>
              )}
              {fileContent && !fileContentError && (
                <pre className="text-sm text-gray-700 font-mono whitespace-pre-wrap break-words leading-relaxed">
                  {fileContent}
                </pre>
              )}
            </div>
          </div>

          {/* 右侧：检索结果 + 图谱 - 42% */}
          <div className="col-span-12 lg:col-span-5 flex flex-col gap-6">
            {/* 检索结果 */}
            <div className="flex-1 bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden flex flex-col min-h-0">
              <div className="px-4 py-3 border-b border-gray-100 bg-gradient-to-r from-indigo-50 to-purple-50">
                <div className="flex items-center gap-2">
                  <span>💡</span>
                  <span className="font-semibold text-gray-800">检索结果</span>
                </div>
              </div>
              <div className="flex-1 overflow-y-auto p-4">
                {renderSearchResult()}
              </div>
            </div>

            {/* 知识图谱 */}
            <div className="h-64 lg:h-72 bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden flex flex-col">
              <div className="px-4 py-3 border-b border-gray-100 bg-gradient-to-r from-purple-50 to-pink-50">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <GraphIcon />
                    <span className="font-semibold text-gray-800">知识图谱</span>
                    {graphData && (
                      <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full">
                        {graphData.nodes?.length || 0} 节点
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {graphLoading && (
                      <span className="flex items-center gap-1 text-xs text-gray-500">
                        <LoadingIndicator />
                      </span>
                    )}
                    <button
                      onClick={() => setGraphExpanded(true)}
                      className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors text-gray-500 hover:text-gray-700"
                      title="全屏查看"
                    >
                      <ExpandIcon />
                    </button>
                  </div>
                </div>
              </div>
              {graphError && (
                <div className="px-4 py-2 bg-red-50 text-red-600 text-sm">
                  {graphError}
                </div>
              )}
              <div className="flex-1 bg-gray-50/50 flex flex-col">
                {/* 切换按钮 */}
                {searchGraphData && fullGraphData && (
                  <div className="px-3 py-2 border-b border-gray-200 bg-white flex items-center gap-2">
                    <button
                      onClick={() => {
                        setShowSearchGraph(!showSearchGraph);
                        setGraphData(showSearchGraph ? fullGraphData : searchGraphData);
                      }}
                      className={`px-2.5 py-1 text-xs rounded-lg transition-colors ${
                        showSearchGraph 
                          ? 'bg-indigo-600 text-white' 
                          : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                      }`}
                    >
                      {showSearchGraph ? '完整图谱' : '搜索结果'}
                    </button>
                    {showSearchGraph && searchGraphData && (
                      <span className="text-xs text-gray-500">
                        {searchGraphData.nodes.length}节点/{searchGraphData.links.length}边
                      </span>
                    )}
                    {!showSearchGraph && fullGraphData && (
                      <span className="text-xs text-gray-500">
                        {fullGraphData.nodes.length}节点/{fullGraphData.links.length}边
                      </span>
                    )}
                  </div>
                )}
                <div className="flex-1">
                  {graphData ? (
                    <GraphVisualization
                      key={`${showSearchGraph ? 'search' : 'full'}-${graphData.nodes?.length}`}
                      ref={graphRef as MutableRefObject<GraphVisualizationAPI>}
                      data={graphData as unknown as GraphData<NodeObject, LinkObject>}
                      graphControls={graphControlsRef as MutableRefObject<GraphControlsAPI>}
                      className="w-full h-full"
                    />
                  ) : (
                    <div className="w-full h-full flex flex-col items-center justify-center text-center p-4">
                      <div className="w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center mb-3">
                        <GraphIcon />
                      </div>
                      <p className="text-sm text-gray-500">暂无图数据</p>
                      <p className="text-xs text-gray-400 mt-1">请先执行 cognify 流程</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}