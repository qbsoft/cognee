"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import apiFetch from "@/utils/fetch";
import { CTAButton, GhostButton } from "@/ui/elements";
import { LoadingIndicator } from "@/ui/App";

// 图标组件
const BackIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
  </svg>
);

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

const RefreshIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
  </svg>
);

const TrashIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
  </svg>
);

const CheckIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
  </svg>
);

const ClockIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const AlertIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

interface DatasetDetailPageProps {
  params: Promise<{
    datasetId: string;
  }>;
}

interface Dataset {
  id: string;
  name: string;
  created_at: string;
  updated_at?: string | null;
}

interface StageStatus {
  status: "pending" | "in_progress" | "completed" | "failed";
  progress?: number;
  started_at?: string;
  completed_at?: string;
  error?: string;
}

interface PipelineStatus {
  parsing?: StageStatus;
  chunking?: StageStatus;
  graph_indexing?: StageStatus;  // 后端返回下划线命名
  vector_indexing?: StageStatus; // 后端返回下划线命名
}

interface DataStats {
  chunkCount?: number | null;
  nodeCount?: number | null;
  edgeCount?: number | null;
  vectorCount?: number | null;
}

interface DataFile {
  id: string;
  name: string;
  extension: string;
  mimeType: string;
  dataSize?: number | null;
  tokenCount?: number | null;
  created_at: string;
  updated_at?: string | null;
  pipeline_status?: PipelineStatus;
  stats?: DataStats;
}

// Server Component
export default function DatasetDetailPage({ params }: DatasetDetailPageProps) {
  const unwrappedParams = React.use(params);
  return <DatasetDetailPageClient datasetId={unwrappedParams.datasetId} />;
}

// Client Component
function DatasetDetailPageClient({ datasetId }: { datasetId: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [files, setFiles] = useState<DataFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());
  const [actionLoading, setActionLoading] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const [pollingIntervalId, setPollingIntervalId] = useState<NodeJS.Timeout | null>(null);
  const [autoPolling, setAutoPolling] = useState(false);
  const autoPollingTimerRef = useRef<NodeJS.Timeout | null>(null);
  const [processingProgress, setProcessingProgress] = useState<{
    total: number;
    completed: number;
    inProgress: number;
    pending: number;
    startTime: number | null;
  }>({ total: 0, completed: 0, inProgress: 0, pending: 0, startTime: null });

  const loadDataset = useCallback(async () => {
    try {
      const response = await apiFetch("/v1/datasets", {
        headers: { "Content-Type": "application/json" },
      });
      const datasets: Dataset[] = await response.json();
      const current = datasets.find((d) => d.id === datasetId);
      if (current) {
        setDataset(current);
      }
    } catch (error: any) {
      console.error("加载数据集信息失败:", error);
    }
  }, [datasetId]);

  const loadFiles = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiFetch(`/v1/datasets/${datasetId}/data`, {
        headers: { "Content-Type": "application/json" },
      });
      const data: DataFile[] = await response.json();
      console.log("[loadFiles] 加载文件列表:", data.length, "个文件");
      // 输出第一个文件的状态供调试
      if (data.length > 0) {
        console.log("[loadFiles] 第一个文件状态:", data[0].pipeline_status);
      }
      setFiles(data);
    } catch (error: any) {
      console.error("[加载文件列表失败]", error);
      setError(error?.message || "加载文件列表失败");
    } finally {
      setLoading(false);
    }
  }, [datasetId]);

  useEffect(() => {
    loadDataset();
    loadFiles();
  }, [loadDataset, loadFiles]);

  // 从上传/处理页面导航过来时，自动启动轮询
  useEffect(() => {
    if (searchParams.get("processing") === "true") {
      setAutoPolling(true);
    }
  }, [searchParams]);

  // 自动轮询逻辑：每 3 秒刷新一次文件状态，直到所有阶段完成
  useEffect(() => {
    if (!autoPolling) return;

    // 检查是否还有文件处于处理中状态
    const stages = ["parsing", "chunking", "graph_indexing", "vector_indexing"] as const;
    const hasProcessingFiles = files.some((file) =>
      stages.some((stage) => {
        const s = file.pipeline_status?.[stage]?.status;
        return s === "in_progress" || s === "pending";
      })
    );
    const hasCompletedFiles = files.some((file) =>
      stages.some((stage) => {
        const s = file.pipeline_status?.[stage]?.status;
        return s === "completed" || s === "failed";
      })
    );

    // 所有文件都已处理完，停止自动轮询
    if (!hasProcessingFiles && hasCompletedFiles) {
      setAutoPolling(false);
      return;
    }

    // 继续轮询
    autoPollingTimerRef.current = setTimeout(() => {
      loadFiles();
    }, 3000);

    return () => {
      if (autoPollingTimerRef.current) {
        clearTimeout(autoPollingTimerRef.current);
      }
    };
  }, [autoPolling, files, loadFiles]);

  // 组件卸载时清理自动轮询定时器
  useEffect(() => {
    return () => {
      if (autoPollingTimerRef.current) {
        clearTimeout(autoPollingTimerRef.current);
      }
    };
  }, []);

  const toggleFileSelection = (fileId: string) => {
    setSelectedFiles(prev => {
      const newSet = new Set(prev);
      if (newSet.has(fileId)) {
        newSet.delete(fileId);
      } else {
        newSet.add(fileId);
      }
      return newSet;
    });
  };

  const toggleSelectAll = () => {
    if (selectedFiles.size === files.length) {
      setSelectedFiles(new Set());
    } else {
      setSelectedFiles(new Set(files.map(f => f.id)));
    }
  };

  const handleReprocess = async () => {
    if (files.length === 0) {
      alert("当前数据集没有文件，无需重新处理。");
      return;
    }
    
    if (!confirm(`确定要重新处理当前数据集下的所有 ${files.length} 个文件吗？\n\n这将重新执行解析、切片和索引流程，以保证数据一致性。`)) {
      return;
    }

    setActionLoading(true);
    console.log("[handleReprocess] 开始重新处理...");
    try {
      const allFileIds = files.map((file) => file.id);
      console.log("[handleReprocess] 文件IDs:", allFileIds);
      
      const url = `/v1/datasets/${datasetId}/reprocess`;
      const requestBody = {
        data_ids: allFileIds,
        run_in_background: true
      };
      console.log("[handleReprocess] 请求URL:", url);
      console.log("[handleReprocess] 请求体:", requestBody);
      
      const response = await apiFetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody)
      });
      
      console.log("[handleReprocess] 响应状态:", response.status);
      
      const result = await response.json();
      console.log("[handleReprocess] Pipeline Run ID:", result.pipelineRunId);
      
      // 初始化进度状态
      setProcessingProgress({ 
        total: allFileIds.length, 
        completed: 0, 
        inProgress: allFileIds.length, 
        pending: 0,
        startTime: Date.now()
      });
      
      // 使用WebSocket订阅实时进度更新
      startWebSocketProgress(result.pipelineRunId, allFileIds);
    } catch (error: any) {
      console.error("重新处理失败:", error);
      alert(`重新处理失败: ${error?.message || "未知错误"}`);
    } finally {
      setActionLoading(false);
    }
  };

  // WebSocket实时进度订阅
  const startWebSocketProgress = (pipelineRunId: string, fileIds: string[]) => {
    setIsPolling(true);
    
    // 从localStorage获取token(登录时存储)
    const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
    
    if (!token) {
      console.error('[WebSocket] 未找到认证token');
      console.warn('[WebSocket] 请确保已登录并重新刷新页面');
      setIsPolling(false);
      alert('⚠️ 无法获取认证信息\n\n请重新登录后再试。');
      return;
    }
    
    // 构建 WebSocket URL，将token作为查询参数
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = process.env.NEXT_PUBLIC_BACKEND_API_URL?.replace('http://', '').replace('https://', '') || 'localhost:8000';
    const wsUrl = `${wsProtocol}//${wsHost}/api/v1/cognify/subscribe/${pipelineRunId}?token=${encodeURIComponent(token)}`;
    
    console.log('[WebSocket] 连接到:', wsUrl.replace(token, '***'));
    
    let ws: WebSocket | null = null;
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 3;
    
    const connect = () => {
      try {
        ws = new WebSocket(wsUrl);
        
        ws.onopen = () => {
          console.log('[WebSocket] ✅ 连接成功');
          reconnectAttempts = 0;
        };
        
        ws.onmessage = async (event) => {
          try {
            const data = JSON.parse(event.data);
            console.log('[WebSocket] 收到消息:', data.status);
            
            // 刷新文件列表获取最新状态
            const response = await apiFetch(`/v1/datasets/${datasetId}/data`);
            const currentFiles: DataFile[] = await response.json();
            setFiles(currentFiles);
            
            const selectedData = currentFiles.filter(f => fileIds.includes(f.id));
            
            let completedCount = 0;
            selectedData.forEach(file => {
              const stages = ["parsing", "chunking", "graph_indexing", "vector_indexing"] as const;
              const allStagesCompleted = stages.every(stage => 
                file.pipeline_status?.[stage]?.status === "completed"
              );
              if (allStagesCompleted) completedCount++;
            });
            
            // 更新进度
            setProcessingProgress(prev => ({
              ...prev,
              completed: completedCount,
              inProgress: selectedData.length - completedCount
            }));
            
            console.log(`[WebSocket] 进度: ${completedCount}/${selectedData.length}`);
            
            // 检查是否完成
            if (data.status === 'PipelineRunCompleted' || completedCount === selectedData.length) {
              console.log('[WebSocket] ✅ 处理完成');
              setIsPolling(false);
              if (ws) ws.close();
            }
          } catch (error) {
            console.error('[WebSocket] 处理消息失败:', error);
          }
        };
        
        ws.onerror = (error) => {
          console.error('[WebSocket] ❗ 错误:', error);
        };
        
        ws.onclose = (event) => {
          console.log('[WebSocket] 连接关闭:', event.code, event.reason);
          
          // 如果是正常关闭或已完成,不重连
          if (event.code === 1000 || !isPolling) {
            setIsPolling(false);
            return;
          }
          
          // 如果是未授权错误
          if (event.code === 1008) {
            console.error('[WebSocket] 认证失败');
            setIsPolling(false);
            alert('认证失败，请重新登录');
            return;
          }
          
          // 尝试重连
          if (reconnectAttempts < maxReconnectAttempts) {
            reconnectAttempts++;
            console.log(`[WebSocket] 尝试重连 (${reconnectAttempts}/${maxReconnectAttempts})...`);
            setTimeout(connect, 2000 * reconnectAttempts);
          } else {
            console.error('[WebSocket] 重连失败');
            setIsPolling(false);
            alert('连接失败，请刷新页面重试');
          }
        };
      } catch (error) {
        console.error('[WebSocket] 创建连接失败:', error);
        setIsPolling(false);
        alert('连接失败，请刷新页面重试');
      }
    };
    
    // 启动连接
    connect();
    
    // 组件卸载时清理
    return () => {
      if (ws) ws.close();
    };
  };

  // 组件卸载时清理轮询
  useEffect(() => {
    return () => {
      if (pollingIntervalId) {
        clearInterval(pollingIntervalId);
      }
    };
  }, [pollingIntervalId]);

  const handleDelete = async () => {
    if (selectedFiles.size === 0) return;
    
    if (!confirm(`⚠️ 警告：确定要删除选中的 ${selectedFiles.size} 个文件吗？\n\n这将永久删除文件及其所有关联数据（切片、图节点、向量索引），操作不可恢复！`)) {
      return;
    }

    setActionLoading(true);
    try {
      const response = await apiFetch(`/v1/datasets/${datasetId}/data/batch-delete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          data_ids: Array.from(selectedFiles),
          mode: "soft"
        })
      });
      
      const result = await response.json();
      alert(`删除成功！\n已删除: ${result.deletedCount} 个文件\n删除的chunks: ${result.deletedChunkCount}\n删除的nodes: ${result.deletedNodeCount}`);
      setSelectedFiles(new Set());
      // 刷新列表
      loadFiles();
    } catch (error: any) {
      alert(`删除失败: ${error?.message || "未知错误"}`);
    } finally {
      setActionLoading(false);
    }
  };

  const getStatusBadge = (stageStatus: StageStatus | undefined) => {
    const status = stageStatus?.status || "pending";
    
    const styles: Record<string, string> = {
      pending: "bg-gray-100 text-gray-600",
      in_progress: "bg-blue-100 text-blue-700 animate-pulse",
      completed: "bg-green-100 text-green-700",
      failed: "bg-red-100 text-red-700"
    };
    const labels: Record<string, string> = {
      pending: "待处理",
      in_progress: "处理中",
      completed: "已完成",
      failed: "失败"
    };

    // 根据状态动态渲染图标,避免创建不稳定的对象引用
    const renderIcon = () => {
      switch (status) {
        case "in_progress": return <LoadingIndicator key="icon" />;
        case "completed": return <CheckIcon key="icon" />;
        case "failed": return <AlertIcon key="icon" />;
        default: return <ClockIcon key="icon" />;
      }
    };

    return (
      <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${styles[status] || styles.pending}`}>
        {renderIcon()}
        {labels[status] || status}
      </span>
    );
  };

  const renderFileList = () => {
    if (loading) {
      return (
        <div className="flex items-center justify-center py-12">
          <LoadingIndicator />
          <span className="ml-2 text-gray-500">加载中...</span>
        </div>
      );
    }

    if (error) {
      return (
        <div className="text-center py-12">
          <p className="text-red-600 mb-4">{error}</p>
          <GhostButton onClick={loadFiles}>重试</GhostButton>
        </div>
      );
    }

    if (files.length === 0) {
      return (
        <div className="text-center py-12 text-gray-500">
          <FileIcon />
          <p className="mt-2">暂无文件</p>
        </div>
      );
    }

    return (
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="px-4 py-3 text-left">
                <input
                  type="checkbox"
                  checked={selectedFiles.size === files.length && files.length > 0}
                  onChange={toggleSelectAll}
                  className="rounded border-gray-300 focus:ring-indigo-500"
                />
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">文件名</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">解析</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">切片</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">图索引</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">向量索引</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">统计</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {files.map((file) => (
              <tr key={file.id} className={`hover:bg-gray-50 transition-colors ${selectedFiles.has(file.id) ? "bg-indigo-50" : ""}`}>
                <td className="px-4 py-3">
                  <input
                    type="checkbox"
                    checked={selectedFiles.has(file.id)}
                    onChange={() => toggleFileSelection(file.id)}
                    className="rounded border-gray-300 focus:ring-indigo-500"
                  />
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <FileIcon />
                    <div>
                      <div className="font-medium text-gray-900 text-sm">{file.name}</div>
                      <div className="text-xs text-gray-500">{file.extension}</div>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3">{getStatusBadge(file.pipeline_status?.parsing)}</td>
                <td className="px-4 py-3">{getStatusBadge(file.pipeline_status?.chunking)}</td>
                <td className="px-4 py-3">{getStatusBadge(file.pipeline_status?.graph_indexing)}</td>
                <td className="px-4 py-3">{getStatusBadge(file.pipeline_status?.vector_indexing)}</td>
                <td className="px-4 py-3">
                  <div className="text-xs text-gray-600 space-y-1">
                    {file.stats?.chunkCount != null && <div>Chunks: {file.stats.chunkCount}</div>}
                    {file.stats?.nodeCount != null && <div>Nodes: {file.stats.nodeCount}</div>}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-indigo-50/30 to-purple-50/30">
      {/* 顶部导航栏 */}
      <div className="sticky top-0 z-40 bg-white/80 backdrop-blur-md border-b border-gray-200/50">
        <div className="max-w-7xl mx-auto px-6 py-4">
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
                <div className="text-xs text-indigo-600 font-medium">数据集管理</div>
                <div className="text-lg font-bold text-gray-900">
                  {dataset?.name || "加载中..."}
                </div>
              </div>
            </div>
            <button
              onClick={() => router.push(`/datasets/${datasetId}/search`)}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
            >
              <SearchIcon />
              <span>检索查询</span>
            </button>
          </div>
        </div>
      </div>

      {/* 主内容区域 */}
      <div className="max-w-7xl mx-auto px-6 py-6">
        {/* 操作栏 */}
        <div className="mb-6 bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-sm text-gray-600">
                已选择 <span className="font-bold text-indigo-600">{selectedFiles.size}</span> 个文件
              </span>
              {(isPolling || autoPolling) && (
                <span className="flex items-center gap-2 text-xs text-blue-600 bg-blue-50 px-3 py-1 rounded-full animate-pulse">
                  <LoadingIndicator />
                  <span>{isPolling ? "正在监控处理进度..." : "处理中，自动刷新..."}</span>
                </span>
              )}
            </div>
            <div className="flex items-center gap-3">
              <GhostButton onClick={loadFiles} disabled={loading}>
                <RefreshIcon />
                <span>刷新</span>
              </GhostButton>
              <CTAButton
                onClick={handleReprocess}
                disabled={files.length === 0 || actionLoading}
                className="bg-blue-600 hover:bg-blue-700"
              >
                <RefreshIcon />
                <span>重新处理整个数据集</span>
              </CTAButton>
              <CTAButton
                onClick={handleDelete}
                disabled={selectedFiles.size === 0 || actionLoading}
                className="bg-red-600 hover:bg-red-700"
              >
                <TrashIcon />
                <span>删除</span>
              </CTAButton>
            </div>
          </div>
        </div>

        {/* 处理进度提示 - 简化版 */}
        {isPolling && processingProgress.total > 0 && (
          <div className="mb-6 bg-blue-50 border-l-4 border-blue-500 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <LoadingIndicator />
                <div>
                  <div className="text-sm font-medium text-blue-900">
                    正在处理数据集...
                  </div>
                  <div className="text-xs text-blue-700 mt-1">
                    已完成 <span className="font-bold">{processingProgress.completed}</span> / {processingProgress.total} 个文件
                    {processingProgress.inProgress > 0 && (
                      <span className="ml-2">· {processingProgress.inProgress} 个文件处理中</span>
                    )}
                  </div>
                </div>
              </div>
              {processingProgress.startTime && (
                <div className="text-xs text-blue-600">
                  已用时: {Math.round((Date.now() - processingProgress.startTime) / 1000)}秒
                </div>
              )}
            </div>
          </div>
        )}

        {/* 文件列表 */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100 bg-gradient-to-r from-gray-50 to-white">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileIcon />
                <span className="font-semibold text-gray-800">文件列表</span>
                <span className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded-full">
                  {files.length} 个文件
                </span>
              </div>
            </div>
          </div>
          {renderFileList()}
        </div>
      </div>
    </div>
  );
}

