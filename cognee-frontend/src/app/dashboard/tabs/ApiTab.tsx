"use client";

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { fetch as apiFetch } from "@/utils";
import StatusDot from "@/ui/elements/StatusDot";

interface EndpointInfo {
  method: "GET" | "POST" | "DELETE";
  path: string;
  descKey: string;
  curl: string;
}

const ENDPOINTS: EndpointInfo[] = [
  {
    method: "POST",
    path: "/api/v1/add",
    descKey: "dashboard.api.endpoints.add",
    curl: `curl -X POST http://localhost:8000/api/v1/add \
  -H "Content-Type: application/json" \
  -d '{"data": "your text here", "dataset_name": "my_dataset"}'`,
  },
  {
    method: "POST",
    path: "/api/v1/cognify",
    descKey: "dashboard.api.endpoints.cognify",
    curl: `curl -X POST http://localhost:8000/api/v1/cognify \
  -H "Content-Type: application/json" \
  -d '{"datasets": ["my_dataset"]}'`,
  },
  {
    method: "POST",
    path: "/api/v1/search",
    descKey: "dashboard.api.endpoints.search",
    curl: `curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "your question", "search_type": "GRAPH_COMPLETION"}'`,
  },
  {
    method: "GET",
    path: "/api/v1/datasets",
    descKey: "dashboard.api.endpoints.datasets",
    curl: `curl -X GET http://localhost:8000/api/v1/datasets`,
  },
  {
    method: "GET",
    path: "/api/v1/datasets/{id}/data",
    descKey: "dashboard.api.endpoints.datasetData",
    curl: `curl -X GET http://localhost:8000/api/v1/datasets/{id}/data`,
  },
  {
    method: "DELETE",
    path: "/api/v1/delete",
    descKey: "dashboard.api.endpoints.delete",
    curl: `curl -X DELETE http://localhost:8000/api/v1/delete \
  -H "Content-Type: application/json" \
  -d '{"dataset_name": "my_dataset"}'`,
  },
  {
    method: "GET",
    path: "/api/v1/settings",
    descKey: "dashboard.api.endpoints.settings",
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
results = await cognee.search("GRAPH_COMPLETION", query="your question")`;

function copyToClipboard(text: string) {
  navigator.clipboard.writeText(text);
}

export default function ApiTab() {
  const { t } = useTranslation();
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
        <h2 className="text-lg font-semibold text-gray-800 mb-3">{t("dashboard.api.serviceStatus")}</h2>
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4 flex items-center gap-3">
            <StatusDot isActive={backendUp} />
            <div>
              <div className="font-medium text-gray-800">{t("dashboard.api.backendService")}</div>
              <div className="text-xs text-gray-500">
                {backendUp ? t("common.connected") : t("common.notConnected")}
              </div>
            </div>
          </div>
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4 flex items-center gap-3">
            <StatusDot isActive={mcpUp} />
            <div>
              <div className="font-medium text-gray-800">{t("dashboard.api.mcpService")}</div>
              <div className="text-xs text-gray-500">
                {mcpUp ? t("common.connected") : t("common.notConnected")}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Swagger Link */}
      <section>
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5 flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-gray-800">{t("dashboard.api.swaggerTitle")}</h3>
            <p className="text-sm text-gray-500 mt-1">
              {t("dashboard.api.swaggerDescription")}
            </p>
          </div>
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors whitespace-nowrap"
          >
            {t("dashboard.api.openSwagger")}
          </a>
        </div>
      </section>

      {/* Core API Endpoints */}
      <section>
        <h2 className="text-lg font-semibold text-gray-800 mb-3">
          {t("dashboard.api.coreEndpoints")}
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
              <p className="text-sm text-gray-600 mb-3">{t(ep.descKey)}</p>
              <div className="relative">
                <pre className="bg-gray-900 text-gray-100 rounded-lg p-3 text-xs font-mono overflow-x-auto">
                  {ep.curl}
                </pre>
                <button
                  onClick={() => handleCopyCurl(idx, ep.curl)}
                  className="absolute top-2 right-2 px-2 py-1 text-xs bg-gray-700 text-gray-300 rounded hover:bg-gray-600 transition-colors"
                >
                  {copiedIndex === idx ? t("common.copied") : t("common.copy")}
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Python SDK Quick Start */}
      <section>
        <h2 className="text-lg font-semibold text-gray-800 mb-3">
          {t("dashboard.api.pythonSdk")}
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
              {sdkCopied ? t("common.copied") : t("common.copy")}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
