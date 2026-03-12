"use client";

import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
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
  const { t } = useTranslation();

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
      console.error("Failed to fetch API Keys:", error);
      toast.error("Failed to fetch API Keys");
    } finally {
      setLoading(false);
    }
  };

  const handleCreateKey = async () => {
    if (!newKeyData.name.trim()) {
      toast.error(t("tenantAdmin.apiKeys.keyNameFormLabel"));
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
        toast.success(t("tenantAdmin.apiKeys.keyCreatedMsg"));
        setShowCreateForm(false);
        setNewKeyData({ name: "", expires_in_days: "" });
        await fetchApiKeys();
      } else {
        const data = await response.json();
        toast.error(data.detail || "Create failed");
      }
    } catch (error) {
      console.error("Failed to create API Key:", error);
      toast.error("Create failed, please try again later");
    } finally {
      setCreating(false);
    }
  };

  const handleToggleActive = async (keyId: string, currentActive: boolean) => {
    const action = currentActive ? t("tenantAdmin.apiKeys.disable") : t("tenantAdmin.apiKeys.enable");
    if (!confirm(`${action} this API Key?`)) {
      return;
    }

    try {
      const response = await fetch(`/v1/api-keys/${keyId}/active`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: !currentActive }),
      });

      if (response.ok) {
        toast.success(`${action} OK`);
        await fetchApiKeys();
      } else {
        const data = await response.json();
        toast.error(data.detail || `${action} failed`);
      }
    } catch (error) {
      console.error(`${action} failed:`, error);
      toast.error(`${action} failed, please try again later`);
    }
  };

  const handleRevokeKey = async (keyId: string, keyName: string) => {
    if (!confirm(`${t("tenantAdmin.apiKeys.revoke")} API Key "${keyName}"?\n\nThis action cannot be undone!`)) {
      return;
    }

    try {
      const response = await fetch(`/v1/api-keys/${keyId}`, {
        method: "DELETE",
      });

      if (response.ok) {
        toast.success(t("tenantAdmin.apiKeys.revoke") + " OK");
        await fetchApiKeys();
      } else {
        const data = await response.json();
        toast.error(data.detail || "Revoke failed");
      }
    } catch (error) {
      console.error("Revoke failed:", error);
      toast.error("Revoke failed, please try again later");
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success(t("tenantAdmin.apiKeys.copiedToClipboard"));
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString();
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
      {/* Key created success banner */}
      {createdKey && (
        <div className="bg-yellow-50 border-2 border-yellow-400 rounded-lg p-6">
          <div className="flex items-start">
            <div className="flex-shrink-0">
              <svg className="h-6 w-6 text-yellow-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <div className="ml-3 flex-1">
              <h3 className="text-lg font-medium text-yellow-900">{t("tenantAdmin.apiKeys.importantSave")}</h3>
              <div className="mt-2 text-sm text-yellow-800">
                <p>{t("tenantAdmin.apiKeys.keyCreatedMsg")}</p>
              </div>
              <div className="mt-4">
                <div className="bg-white rounded-lg p-4 border border-yellow-300">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-gray-700">{t("tenantAdmin.apiKeys.keyNameLabel")}</span>
                    <span className="text-sm text-gray-900">{createdKey.name}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-700">{t("tenantAdmin.apiKeys.apiKeyLabel")}</span>
                    <div className="flex items-center space-x-2">
                      <code className="text-sm bg-gray-100 px-3 py-1 rounded font-mono">
                        {createdKey.key}
                      </code>
                      <button
                        onClick={() => copyToClipboard(createdKey.key)}
                        className="text-indigo-600 hover:text-indigo-800 text-sm font-medium"
                      >
                        {t("tenantAdmin.apiKeys.copy")}
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
                  {t("tenantAdmin.apiKeys.savedDismiss")}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Page description */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h3 className="text-sm font-medium text-blue-900 mb-2">{t("tenantAdmin.apiKeys.whatIsApiKey")}</h3>
        <p className="text-sm text-blue-800">
          {t("tenantAdmin.apiKeys.apiKeyDesc")}
        </p>
      </div>

      {/* Create button and form */}
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-semibold text-gray-900">{t("tenantAdmin.apiKeys.manageTitle")}</h2>
        {!showCreateForm && (
          <CTAButton onClick={() => setShowCreateForm(true)}>
            {t("tenantAdmin.apiKeys.createButton")}
          </CTAButton>
        )}
      </div>

      {showCreateForm && (
        <div className="bg-white border border-gray-300 rounded-lg p-6 shadow-sm">
          <h3 className="text-lg font-medium text-gray-900 mb-4">{t("tenantAdmin.apiKeys.createFormTitle")}</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {t("tenantAdmin.apiKeys.keyNameFormLabel")}
              </label>
              <input
                type="text"
                value={newKeyData.name}
                onChange={(e) => setNewKeyData({ ...newKeyData, name: e.target.value })}
                placeholder={t("tenantAdmin.apiKeys.keyNamePlaceholder")}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <p className="mt-1 text-xs text-gray-500">
                {t("tenantAdmin.apiKeys.keyNameHint")}
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {t("tenantAdmin.apiKeys.validityLabel")}
              </label>
              <input
                type="number"
                value={newKeyData.expires_in_days}
                onChange={(e) => setNewKeyData({ ...newKeyData, expires_in_days: e.target.value })}
                placeholder={t("tenantAdmin.apiKeys.validityPlaceholder")}
                min="1"
                max="3650"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <p className="mt-1 text-xs text-gray-500">
                {t("tenantAdmin.apiKeys.validityHint")}
              </p>
            </div>
            <div className="flex space-x-3">
              <CTAButton
                onClick={handleCreateKey}
                disabled={creating || !newKeyData.name.trim()}
              >
                {creating ? t("tenantAdmin.apiKeys.creating") : t("tenantAdmin.apiKeys.create")}
              </CTAButton>
              <button
                onClick={() => {
                  setShowCreateForm(false);
                  setNewKeyData({ name: "", expires_in_days: "" });
                }}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
              >
                {t("tenantAdmin.apiKeys.cancel")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* API Keys list */}
      {apiKeys.length === 0 ? (
        <div className="text-center py-12 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
          <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-gray-900">{t("tenantAdmin.apiKeys.noApiKeys")}</h3>
          <p className="mt-1 text-sm text-gray-500">{t("tenantAdmin.apiKeys.noApiKeysHint")}</p>
        </div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t("tenantAdmin.apiKeys.colName")}
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t("tenantAdmin.apiKeys.colPrefix")}
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t("tenantAdmin.apiKeys.colStatus")}
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t("tenantAdmin.apiKeys.colLastUsed")}
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t("tenantAdmin.apiKeys.colExpiry")}
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t("tenantAdmin.apiKeys.colActions")}
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {apiKeys.map((key) => (
                <tr key={key.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-medium text-gray-900">{key.name}</div>
                    <div className="text-xs text-gray-500">
                      {t("tenantAdmin.apiKeys.createdAt", { date: formatDate(key.created_at) })}
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
                      {key.is_active ? t("tenantAdmin.apiKeys.enabled") : t("tenantAdmin.apiKeys.disabled")}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {key.last_used_at ? formatDate(key.last_used_at) : t("tenantAdmin.apiKeys.neverUsed")}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {key.expires_at ? formatDate(key.expires_at) : t("tenantAdmin.apiKeys.neverExpires")}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm space-x-3">
                    <button
                      onClick={() => handleToggleActive(key.id, key.is_active)}
                      className={key.is_active ? "text-yellow-600 hover:text-yellow-800" : "text-green-600 hover:text-green-800"}
                    >
                      {key.is_active ? t("tenantAdmin.apiKeys.disable") : t("tenantAdmin.apiKeys.enable")}
                    </button>
                    <button
                      onClick={() => handleRevokeKey(key.id, key.name)}
                      className="text-red-600 hover:text-red-800"
                    >
                      {t("tenantAdmin.apiKeys.revoke")}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Usage instructions */}
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
        <h3 className="text-sm font-medium text-gray-900 mb-2">{t("tenantAdmin.apiKeys.usageTitle")}</h3>
        <div className="text-sm text-gray-700 space-y-3">
          <p><strong>{t("tenantAdmin.apiKeys.usagePython")}</strong></p>
          <pre className="bg-gray-800 text-gray-100 p-3 rounded text-xs overflow-x-auto">
{`import requests

headers = {"X-API-Key": "your_api_key_here"}
response = requests.post(
    "http://localhost:8000/api/v1/cognify",
    json={"dataset_name": "my_dataset"},
    headers=headers
)`}
          </pre>

          <p className="mt-3"><strong>{t("tenantAdmin.apiKeys.usageJava")}</strong></p>
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

          <p className="mt-3"><strong>{t("tenantAdmin.apiKeys.usageCli")}</strong></p>
          <pre className="bg-gray-800 text-gray-100 p-3 rounded text-xs overflow-x-auto">
{`export COGNEE_API_KEY="your_api_key_here"
cognee cognify --dataset my_dataset`}
          </pre>

          <p className="mt-3"><strong>{t("tenantAdmin.apiKeys.usageSecurity")}</strong></p>
          <ul className="list-disc list-inside ml-4 space-y-1">
            <li>{t("tenantAdmin.apiKeys.secTip1")}</li>
            <li>{t("tenantAdmin.apiKeys.secTip2")}</li>
            <li>{t("tenantAdmin.apiKeys.secTip3")}</li>
            <li>{t("tenantAdmin.apiKeys.secTip4")}</li>
            <li>{t("tenantAdmin.apiKeys.secTip5")}</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
