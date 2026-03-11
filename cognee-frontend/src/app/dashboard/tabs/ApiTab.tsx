"use client";

import { useEffect, useState } from "react";
import { fetch as apiFetch } from "@/utils";
import StatusDot from "@/ui/elements/StatusDot";

interface EndpointInfo {
  method: "GET" | "POST" | "DELETE";
  path: string;
  description: string;
  curl: string;
}

const ENDPOINTS: EndpointInfo[] = [
  {
    method: "POST",
    path: "/api/v1/add",
    description: "上传文件或文本数据到数据集",
    curl: `curl -X POST http://localhost:8000/api/v1/add \\
  -H "Content-Type: application/json" \\
  -d '{"data": "your text here", "dataset_name": "my_dataset"}'`,
  },
  {
    method: "POST",
    path: "/api/v1/cognify",
    description: "触发知识图谱构建管道",
    curl: `curl -X POST http://localhost:8000/api/v1/cognify \\
  -H "Content-Type: application/json" \\
  -d '{"datasets": ["my_dataset"]}'`,
  },
  {
    method: "POST",
    path: "/api/v1/search",
    description: "搜索知识库",
    curl: `curl -X POST http://localhost:8000/api/v1/search \\
  -H "Content-Type: application/json" \\
  -d '{"query": "你的问题", "search_type": "GRAPH_COMPLETION"}'`,
  },
  {
    method: "GET",
    path: "/api/v1/datasets",
    description: "获取所有数据集列表",
    curl: `curl -X GET http://localhost:8000/api/v1/datasets`,
  },
  {
    method: "GET",
    path: "/api/v1/datasets/{id}/data",
    description: "获取数据集中的文件列表",
    curl: `curl -X GET http://localhost:8000/api/v1/datasets/{id}/data`,
  },
  {
    method: "DELETE",
    path: "/api/v1/delete",
    description: "删除数据集或数据",
    curl: `curl -X DELETE http://localhost:8000/api/v1/delete \\
  -H "Content-Type: application/json" \\
  -d '{"dataset_name": "my_dataset"}'`,
  },
  {
    method: "GET",
    path: "/api/v1/settings",
    description: "获取当前系统配置",
    curl: `curl -X GET http://localhost:8000/api/v1/settings`,
  },
];

const METHOD_COLORS: Record<string, string> = {
  GET: "bg-green-100 text-green-700",
  POST: "bg-blue-100 text-blue-700",
  DELETE: "bg-red-100 text-red-700",
};

const PYTHON_SDK_EXAMPLE = `import cognee

await cognee.add("your_text_or_file", dataset_name="my_dataset")
await cognee.cognify()
results = await cognee.search("GRAPH_COMPLETION", query="你的问题")`;

function copyToClipboard(text: string) {
  navigator.clipboard.writeText(text);
}

export default function ApiTab() {
  const [backendUp, setBackendUp] = useState(false);
  const [mcpUp, setMcpUp] = useState(false);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
  const [sdkCopied, setSdkCopied] = useState(false);

  useEffect(() => {
    const checkServices = async () => {
      try {
        await apiFetch.checkHealth();
        setBackendUp(true);
      } catch {
        setBackendUp(false);
      }
      try {
        await apiFetch.checkMCPHealth();
        setMcpUp(true);
      } catch {
        setMcpUp(false);
      }
    };

    checkServices();
    const interval = setInterval(checkServices, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleCopyCurl = (index: number, curl: string) => {
    copyToClipboard(curl);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  const handleCopySdk = () => {
    copyToClipboard(PYTHON_SDK_EXAMPLE);
    setSdkCopied(true);
    setTimeout(() => setSdkCopied(false), 2000);
  };

  return (
    <div className="max-w-4xl mx-auto py-6 px-4 space-y-8">
      {/* Connection Status */}
      <section>
        <h2 className="text-lg font-semibold text-gray-800 mb-3">服务状态</h2>
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4 flex items-center gap-3">
            <StatusDot isActive={backendUp} />
            <div>
              <div className="font-medium text-gray-800">后端服务</div>
              <div className="text-xs text-gray-500">
                {backendUp ? "已连接" : "未连接"}
              </div>
            </div>
          </div>
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4 flex items-center gap-3">
            <StatusDot isActive={mcpUp} />
            <div>
              <div className="font-medium text-gray-800">MCP 服务</div>
              <div className="text-xs text-gray-500">
                {mcpUp ? "已连接" : "未连接"}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Swagger Link */}
      <section>
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5 flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-gray-800">Swagger API 文档</h3>
            <p className="text-sm text-gray-500 mt-1">
              查看完整的交互式 API 文档，支持在线测试接口
            </p>
          </div>
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors whitespace-nowrap"
          >
            打开 Swagger UI &rarr;
          </a>
        </div>
      </section>

      {/* Core API Endpoints */}
      <section>
        <h2 className="text-lg font-semibold text-gray-800 mb-3">
          核心 API 接口
        </h2>
        <div className="space-y-4">
          {ENDPOINTS.map((ep, idx) => (
            <div
              key={idx}
              className="bg-white rounded-xl border border-gray-100 shadow-sm p-4"
            >
              <div className="flex items-center gap-3 mb-2">
                <span
                  className={`inline-block px-2 py-0.5 text-xs font-bold rounded ${METHOD_COLORS[ep.method]}`}
                >
                  {ep.method}
                </span>
                <code className="text-sm font-mono text-gray-700">
                  {ep.path}
                </code>
              </div>
              <p className="text-sm text-gray-600 mb-3">{ep.description}</p>
              <div className="relative">
                <pre className="bg-gray-900 text-gray-100 rounded-lg p-3 text-xs font-mono overflow-x-auto">
                  {ep.curl}
                </pre>
                <button
                  onClick={() => handleCopyCurl(idx, ep.curl)}
                  className="absolute top-2 right-2 px-2 py-1 text-xs bg-gray-700 text-gray-300 rounded hover:bg-gray-600 transition-colors"
                >
                  {copiedIndex === idx ? "已复制" : "复制"}
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Python SDK Quick Start */}
      <section>
        <h2 className="text-lg font-semibold text-gray-800 mb-3">
          Python SDK 快速开始
        </h2>
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4">
          <div className="relative">
            <pre className="bg-gray-900 text-gray-100 rounded-lg p-3 text-xs font-mono overflow-x-auto">
              {PYTHON_SDK_EXAMPLE}
            </pre>
            <button
              onClick={handleCopySdk}
              className="absolute top-2 right-2 px-2 py-1 text-xs bg-gray-700 text-gray-300 rounded hover:bg-gray-600 transition-colors"
            >
              {sdkCopied ? "已复制" : "复制"}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
