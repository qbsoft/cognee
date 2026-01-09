"use client";

import { useState, useEffect } from "react";
import { fetch } from "@/utils";
import { toast } from "react-hot-toast";
import { CTAButton } from "@/ui/elements";

interface ApiKey {
  id: string;
  name: string;
  key_prefix: string;
  is_active: boolean;
  last_used_at: string | null;
  expires_at: string | null;
  created_at: string;
  created_by: string;
}

export default function TenantApiKeysPanel() {
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newKeyData, setNewKeyData] = useState<{
    name: string;
    expires_in_days: string;
  }>({
    name: "",
    expires_in_days: "",
  });
  const [createdKey, setCreatedKey] = useState<{
    key: string;
    name: string;
  } | null>(null);

  useEffect(() => {
    fetchApiKeys();
  }, []);

  const fetchApiKeys = async () => {
    try {
      setLoading(true);
      const response = await fetch("/v1/api-keys");
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      setApiKeys(data.api_keys || []);
    } catch (error) {
      console.error("获取API Keys失败:", error);
      toast.error("获取API Keys失败");
    } finally {
      setLoading(false);
    }
  };

  const handleCreateKey = async () => {
    if (!newKeyData.name.trim()) {
      toast.error("请输入Key名称");
      return;
    }

    try {
      setCreating(true);
      const response = await fetch("/v1/api-keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newKeyData.name,
          expires_in_days: newKeyData.expires_in_days ? parseInt(newKeyData.expires_in_days) : null,
          scopes: [],
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setCreatedKey({
          key: data.api_key.key,
          name: data.api_key.name,
        });
        toast.success("API Key创建成功！");
        setShowCreateForm(false);
        setNewKeyData({ name: "", expires_in_days: "" });
        await fetchApiKeys();
      } else {
        const data = await response.json();
        toast.error(data.detail || "创建失败");
      }
    } catch (error) {
      console.error("创建API Key失败:", error);
      toast.error("创建失败，请稍后重试");
    } finally {
      setCreating(false);
    }
  };

  const handleToggleActive = async (keyId: string, currentActive: boolean) => {
    const action = currentActive ? "禁用" : "启用";
    if (!confirm(`确认要${action}此API Key吗？${currentActive ? '\n\n禁用后，使用此Key的应用将无法访问API。' : ''}`)) {
      return;
    }

    try {
      const response = await fetch(`/v1/api-keys/${keyId}/active`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: !currentActive }),
      });

      if (response.ok) {
        toast.success(`${action}成功！`);
        await fetchApiKeys();
      } else {
        const data = await response.json();
        toast.error(data.detail || `${action}失败`);
      }
    } catch (error) {
      console.error(`${action}失败:`, error);
      toast.error(`${action}失败，请稍后重试`);
    }
  };

  const handleRevokeKey = async (keyId: string, keyName: string) => {
    if (!confirm(`确认要撤销API Key "${keyName}"吗？\n\n⚠️ 此操作不可恢复！撤销后，使用此Key的应用将立即无法访问API。`)) {
      return;
    }

    try {
      const response = await fetch(`/v1/api-keys/${keyId}`, {
        method: "DELETE",
      });

      if (response.ok) {
        toast.success("API Key已撤销！");
        await fetchApiKeys();
      } else {
        const data = await response.json();
        toast.error(data.detail || "撤销失败");
      }
    } catch (error) {
      console.error("撤销失败:", error);
      toast.error("撤销失败，请稍后重试");
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success("已复制到剪贴板！");
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "永不过期";
    return new Date(dateStr).toLocaleString("zh-CN");
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 创建成功提示 */}
      {createdKey && (
        <div className="bg-yellow-50 border-2 border-yellow-400 rounded-lg p-6">
          <div className="flex items-start">
            <div className="flex-shrink-0">
              <svg className="h-6 w-6 text-yellow-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <div className="ml-3 flex-1">
              <h3 className="text-lg font-medium text-yellow-900">⚠️ 重要：请立即保存您的API Key！</h3>
              <div className="mt-2 text-sm text-yellow-800">
                <p>API Key创建成功！出于安全考虑，此Key仅显示一次，关闭后将无法再次查看。</p>
              </div>
              <div className="mt-4">
                <div className="bg-white rounded-lg p-4 border border-yellow-300">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-gray-700">Key名称：</span>
                    <span className="text-sm text-gray-900">{createdKey.name}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-700">API Key：</span>
                    <div className="flex items-center space-x-2">
                      <code className="text-sm bg-gray-100 px-3 py-1 rounded font-mono">
                        {createdKey.key}
                      </code>
                      <button
                        onClick={() => copyToClipboard(createdKey.key)}
                        className="text-indigo-600 hover:text-indigo-800 text-sm font-medium"
                      >
                        复制
                      </button>
                    </div>
                  </div>
                </div>
              </div>
              <div className="mt-4">
                <button
                  onClick={() => setCreatedKey(null)}
                  className="text-sm font-medium text-yellow-900 hover:text-yellow-700"
                >
                  我已保存，关闭此提示 →
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 页面说明 */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h3 className="text-sm font-medium text-blue-900 mb-2">💡 什么是API Keys？</h3>
        <p className="text-sm text-blue-800">
          API Keys用于程序化访问Cognee API，适用于CLI工具、脚本、自动化任务和第三方集成。
          与Cookie/JWT认证相比，API Key更适合长期运行的服务和自动化场景。
        </p>
      </div>

      {/* 创建按钮和表单 */}
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-semibold text-gray-900">API Keys 管理</h2>
        {!showCreateForm && (
          <CTAButton onClick={() => setShowCreateForm(true)}>
            + 创建新的API Key
          </CTAButton>
        )}
      </div>

      {showCreateForm && (
        <div className="bg-white border border-gray-300 rounded-lg p-6 shadow-sm">
          <h3 className="text-lg font-medium text-gray-900 mb-4">创建新的API Key</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Key名称 *
              </label>
              <input
                type="text"
                value={newKeyData.name}
                onChange={(e) => setNewKeyData({ ...newKeyData, name: e.target.value })}
                placeholder="例如：生产环境Key、CLI工具Key"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <p className="mt-1 text-xs text-gray-500">
                为不同用途创建不同的Key，方便管理和追踪
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                有效期（天）
              </label>
              <input
                type="number"
                value={newKeyData.expires_in_days}
                onChange={(e) => setNewKeyData({ ...newKeyData, expires_in_days: e.target.value })}
                placeholder="留空表示永不过期"
                min="1"
                max="3650"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <p className="mt-1 text-xs text-gray-500">
                建议：测试Key设置30天，生产Key可设置365天或永不过期
              </p>
            </div>
            <div className="flex space-x-3">
              <CTAButton
                onClick={handleCreateKey}
                disabled={creating || !newKeyData.name.trim()}
              >
                {creating ? "创建中..." : "创建"}
              </CTAButton>
              <button
                onClick={() => {
                  setShowCreateForm(false);
                  setNewKeyData({ name: "", expires_in_days: "" });
                }}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
              >
                取消
              </button>
            </div>
          </div>
        </div>
      )}

      {/* API Keys列表 */}
      {apiKeys.length === 0 ? (
        <div className="text-center py-12 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
          <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-gray-900">暂无API Keys</h3>
          <p className="mt-1 text-sm text-gray-500">点击上方按钮创建您的第一个API Key</p>
        </div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  名称
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Key前缀
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  状态
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  最后使用
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  过期时间
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  操作
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {apiKeys.map((key) => (
                <tr key={key.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-medium text-gray-900">{key.name}</div>
                    <div className="text-xs text-gray-500">
                      创建于 {formatDate(key.created_at)}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <code className="text-sm bg-gray-100 px-2 py-1 rounded font-mono">
                      {key.key_prefix}
                    </code>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span
                      className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                        key.is_active
                          ? "bg-green-100 text-green-800"
                          : "bg-red-100 text-red-800"
                      }`}
                    >
                      {key.is_active ? "启用" : "禁用"}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {key.last_used_at ? formatDate(key.last_used_at) : "从未使用"}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {formatDate(key.expires_at)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm space-x-3">
                    <button
                      onClick={() => handleToggleActive(key.id, key.is_active)}
                      className={key.is_active ? "text-yellow-600 hover:text-yellow-800" : "text-green-600 hover:text-green-800"}
                    >
                      {key.is_active ? "禁用" : "启用"}
                    </button>
                    <button
                      onClick={() => handleRevokeKey(key.id, key.name)}
                      className="text-red-600 hover:text-red-800"
                    >
                      撤销
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 使用说明 */}
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
        <h3 className="text-sm font-medium text-gray-900 mb-2">📖 使用说明</h3>
        <div className="text-sm text-gray-700 space-y-3">
          <p><strong>1. 在Python脚本中使用：</strong></p>
          <pre className="bg-gray-800 text-gray-100 p-3 rounded text-xs overflow-x-auto">
{`import requests

headers = {"X-API-Key": "your_api_key_here"}
response = requests.post(
    "http://localhost:8000/api/v1/cognify",
    json={"dataset_name": "my_dataset"},
    headers=headers
)`}
          </pre>
          
          <p className="mt-3"><strong>2. 在Java中使用：</strong></p>
          <pre className="bg-gray-800 text-gray-100 p-3 rounded text-xs overflow-x-auto">
{`import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.net.URI;

HttpClient client = HttpClient.newHttpClient();
HttpRequest request = HttpRequest.newBuilder()
    .uri(URI.create("http://localhost:8000/api/v1/cognify"))
    .header("X-API-Key", "your_api_key_here")
    .header("Content-Type", "application/json")
    .POST(HttpRequest.BodyPublishers.ofString(
        "{\"dataset_name\": \"my_dataset\"}"
    ))
    .build();

HttpResponse<String> response = client.send(
    request, 
    HttpResponse.BodyHandlers.ofString()
);`}
          </pre>
          
          <p className="mt-3"><strong>3. 在CLI中使用：</strong></p>
          <pre className="bg-gray-800 text-gray-100 p-3 rounded text-xs overflow-x-auto">
{`export COGNEE_API_KEY="your_api_key_here"
cognee cognify --dataset my_dataset`}
          </pre>
          
          <p className="mt-3"><strong>4. 安全建议：</strong></p>
          <ul className="list-disc list-inside ml-4 space-y-1">
            <li>⚠️ <strong>完整API Key仅在创建时显示一次，请务必立即保存</strong></li>
            <li>不要在代码中硬编码API Key，使用环境变量</li>
            <li>为不同环境（开发/生产）使用不同的Key</li>
            <li>定期轮换API Key以提高安全性</li>
            <li>如果Key泄露，立即撤销并创建新的Key</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
