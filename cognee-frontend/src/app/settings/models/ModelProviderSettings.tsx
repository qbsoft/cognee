"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useTranslation } from "react-i18next";
import { fetch } from "@/utils";
import { useAuthenticatedUser } from "@/modules/auth";
import toast from "react-hot-toast";
import {
  Provider,
  ProviderCategories,
  UserDefaults,
  ConnectionTestResult,
} from "./types";

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function TabButton({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
        active
          ? "border-indigo-600 text-indigo-600"
          : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
      }`}
    >
      {label}
    </button>
  );
}

function StatusBadge({ configured, enabled }: { configured: boolean; enabled: boolean }) {
  const { t } = useTranslation();
  if (!configured) {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600">
        {t("settings.models.status.notConfigured")}
      </span>
    );
  }
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
        enabled
          ? "bg-green-100 text-green-700"
          : "bg-yellow-100 text-yellow-700"
      }`}
    >
      {enabled ? t("settings.models.status.enabled") : t("settings.models.status.disabled")}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Provider Card
// ---------------------------------------------------------------------------

function ProviderCard({
  provider,
  onConfigure,
  onTest,
}: {
  provider: Provider;
  onConfigure: (p: Provider) => void;
  onTest: (p: Provider) => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-lg bg-indigo-50 flex items-center justify-center text-lg font-bold text-indigo-600">
            {provider.icon || provider.name.charAt(0).toUpperCase()}
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">{provider.name}</h3>
            <p className="text-xs text-gray-500">{provider.name_en}</p>
          </div>
        </div>
        <StatusBadge configured={provider.is_configured} enabled={provider.is_enabled} />
      </div>

      {provider.notes && (
        <p className="text-xs text-gray-500 mb-3 line-clamp-2">{provider.notes}</p>
      )}

      {provider.is_configured && provider.api_key_preview && (
        <p className="text-xs text-gray-400 mb-3 font-mono">
          Key: {provider.api_key_preview}
        </p>
      )}

      <div className="flex items-center space-x-2">
        <button
          onClick={() => onConfigure(provider)}
          className="flex-1 px-3 py-1.5 text-sm rounded-lg border border-indigo-300 text-indigo-600 hover:bg-indigo-50 transition-colors"
        >
          {provider.is_configured ? t("settings.models.card.editConfig") : t("settings.models.card.configure")}
        </button>
        {provider.is_configured && (
          <button
            onClick={() => onTest(provider)}
            className="px-3 py-1.5 text-sm rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-50 transition-colors"
          >
            {t("settings.models.card.test")}
          </button>
        )}
      </div>

      {provider.models.length > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-100">
          <p className="text-xs text-gray-400 mb-1">{t("settings.models.card.supportedModels")}</p>
          <div className="flex flex-wrap gap-1">
            {provider.models.slice(0, 4).map((m) => (
              <span
                key={m.id}
                className="inline-block px-1.5 py-0.5 text-xs bg-gray-100 text-gray-600 rounded"
              >
                {m.name}
              </span>
            ))}
            {provider.models.length > 4 && (
              <span className="text-xs text-gray-400">
                +{provider.models.length - 4} more
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Provider Config Modal
// ---------------------------------------------------------------------------

function ProviderConfigModal({
  provider,
  onClose,
  onSaved,
  onDeleted,
}: {
  provider: Provider;
  onClose: () => void;
  onSaved: () => void;
  onDeleted: () => void;
}) {
  const { t } = useTranslation();
  const [apiKey, setApiKey] = useState(provider.api_key_preview || "");
  const [baseUrl, setBaseUrl] = useState(provider.base_url || provider.default_base_url || "");
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<ConnectionTestResult | null>(null);

  const handleSave = async () => {
    setSaving(true);
    try {
      const resp = await fetch(`/v1/model-providers/${provider.id}/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          api_key: apiKey,
          base_url: baseUrl,
          custom_params: {},
        }),
      });
      if (!resp.ok) throw new Error("Save failed");
      toast.success(t("settings.models.modal.saveSuccess"));
      onSaved();
    } catch (e: any) {
      toast.error(e.message || t("settings.models.modal.saveFailed"));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm(t("settings.models.modal.confirmDelete"))) return;
    setDeleting(true);
    try {
      const resp = await fetch(`/v1/model-providers/${provider.id}/config`, {
        method: "DELETE",
      });
      if (!resp.ok) throw new Error("Delete failed");
      toast.success(t("settings.models.modal.deleteSuccess"));
      onDeleted();
    } catch (e: any) {
      toast.error(e.message || t("settings.models.modal.deleteFailed"));
    } finally {
      setDeleting(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const resp = await fetch(`/v1/model-providers/${provider.id}/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          api_key: apiKey,
          base_url: baseUrl,
        }),
      });
      const result: ConnectionTestResult = await resp.json();
      setTestResult(result);
      if (result.success) {
        toast.success(t("settings.models.modal.connectedMs", { ms: result.latency_ms }));
      } else {
        toast.error(result.error || t("settings.models.modal.connectionFailed"));
      }
    } catch (e: any) {
      toast.error(t("settings.models.modal.testReqFailed"));
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-lg bg-indigo-50 flex items-center justify-center text-lg font-bold text-indigo-600">
              {provider.icon || provider.name.charAt(0).toUpperCase()}
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">{provider.name}</h2>
              <p className="text-sm text-gray-500">{provider.name_en}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-4">
          {provider.notes && (
            <div className="p-3 bg-blue-50 rounded-lg text-sm text-blue-700">
              {provider.notes}
            </div>
          )}

          {/* API Key */}
          {provider.auth_type === "api_key" && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                API Key
              </label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={t("settings.models.modal.apiKeyPlaceholder")}
                className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
              />
            </div>
          )}

          {/* Base URL */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {t("settings.models.modal.apiBaseUrl")}
            </label>
            <input
              type="text"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder={provider.default_base_url || "https://api.example.com/v1"}
              className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none font-mono"
            />
            {provider.default_base_url && (
              <p className="mt-1 text-xs text-gray-400">
                {t("settings.models.modal.apiBaseDefault", { url: provider.default_base_url })}
              </p>
            )}
          </div>

          {/* Dynamic config fields */}
          {provider.config_fields
            .filter((f) => f.key !== "api_key" && f.key !== "base_url")
            .map((field) => (
              <div key={field.key}>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {field.label}
                  {field.required && <span className="text-red-500 ml-1">*</span>}
                </label>
                <input
                  type={field.type === "password" ? "password" : "text"}
                  placeholder={field.placeholder}
                  className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
                />
                {field.help_text && (
                  <p className="mt-1 text-xs text-gray-400">{field.help_text}</p>
                )}
              </div>
            ))}

          {/* Test Result */}
          {testResult && (
            <div
              className={`p-3 rounded-lg text-sm ${
                testResult.success
                  ? "bg-green-50 text-green-700 border border-green-200"
                  : "bg-red-50 text-red-700 border border-red-200"
              }`}
            >
              {testResult.success ? (
                <div>
                  <p className="font-medium">{t("settings.models.modal.testSuccess")}</p>
                  <p>{t("settings.models.modal.latency", { ms: testResult.latency_ms })}</p>
                  {testResult.models_discovered && testResult.models_discovered.length > 0 && (
                    <p className="mt-1">
                      {t("settings.models.modal.modelsDiscovered", { count: testResult.models_discovered.length })}
                      {" "}
                      {testResult.models_discovered.slice(0, 5).join(", ")}
                      {testResult.models_discovered.length > 5 && " ..."}
                    </p>
                  )}
                </div>
              ) : (
                <div>
                  <p className="font-medium">{t("settings.models.modal.testFailed")}</p>
                  <p>{testResult.error}</p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-6 border-t border-gray-200">
          <div>
            {provider.is_configured && (
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="px-4 py-2 text-sm text-red-600 hover:text-red-700 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-50"
              >
                {deleting ? t("settings.models.modal.deleting") : t("settings.models.modal.deleteConfig")}
              </button>
            )}
          </div>
          <div className="flex items-center space-x-3">
            <button
              onClick={handleTest}
              disabled={testing}
              className="px-4 py-2 text-sm border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors disabled:opacity-50"
            >
              {testing ? t("settings.models.modal.testing") : t("settings.models.modal.testConnection")}
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-4 py-2 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50"
            >
              {saving ? t("settings.models.modal.saving") : t("settings.models.modal.saveConfig")}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Default Model Selector
// ---------------------------------------------------------------------------

function DefaultModelSelector({
  taskType,
  taskLabel,
  taskDesc,
  allProviders,
  currentDefault,
  onSave,
}: {
  taskType: string;
  taskLabel: string;
  taskDesc: string;
  allProviders: Provider[];
  currentDefault?: { provider_id: string; model_id: string };
  onSave: (taskType: string, providerId: string, modelId: string) => void;
}) {
  const { t } = useTranslation();
  const configuredProviders = allProviders.filter((p) => p.is_configured && p.is_enabled);
  const [selectedProvider, setSelectedProvider] = useState(currentDefault?.provider_id || "");
  const [selectedModel, setSelectedModel] = useState(currentDefault?.model_id || "");

  useEffect(() => {
    setSelectedProvider(currentDefault?.provider_id || "");
    setSelectedModel(currentDefault?.model_id || "");
  }, [currentDefault]);

  const provider = allProviders.find((p) => p.id === selectedProvider);
  const models = provider?.models || [];

  const handleProviderChange = (pid: string) => {
    setSelectedProvider(pid);
    const prov = allProviders.find((p) => p.id === pid);
    const defaultModel = prov?.models.find((m) => m.is_default);
    setSelectedModel(defaultModel?.id || prov?.models[0]?.id || "");
  };

  const hasChanged =
    selectedProvider !== (currentDefault?.provider_id || "") ||
    selectedModel !== (currentDefault?.model_id || "");

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <div className="mb-3">
        <h4 className="font-medium text-gray-900">{taskLabel}</h4>
        <p className="text-xs text-gray-500">{taskDesc}</p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">{t("settings.models.defaults.provider")}</label>
          <select
            value={selectedProvider}
            onChange={(e) => handleProviderChange(e.target.value)}
            className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none"
          >
            <option value="">{t("settings.models.defaults.useSystemDefault")}</option>
            {configuredProviders.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">{t("settings.models.defaults.model")}</label>
          <select
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            disabled={!selectedProvider}
            className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 disabled:bg-gray-50 disabled:text-gray-400 outline-none"
          >
            <option value="">{t("settings.models.defaults.selectModel")}</option>
            {models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
            {selectedModel && !models.find((m) => m.id === selectedModel) && (
              <option value={selectedModel}>{selectedModel}</option>
            )}
          </select>
        </div>
      </div>

      {hasChanged && selectedProvider && selectedModel && (
        <div className="mt-3 flex justify-end">
          <button
            onClick={() => onSave(taskType, selectedProvider, selectedModel)}
            className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
          >
            {t("settings.models.defaults.save")}
          </button>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function ModelProviderSettings() {
  const { t } = useTranslation();
  const router = useRouter();
  const { user } = useAuthenticatedUser();
  const [activeTab, setActiveTab] = useState<"providers" | "defaults">("providers");
  const [categories, setCategories] = useState<ProviderCategories>({});
  const [defaults, setDefaults] = useState<UserDefaults>({});
  const [loading, setLoading] = useState(true);
  const [configuring, setConfiguring] = useState<Provider | null>(null);

  // user is referenced to keep auth check active
  void user;

  const allProviders = Object.values(categories).flatMap((cat) => cat.providers);

  const fetchProviders = useCallback(async () => {
    try {
      const resp = await Promise.race([
        fetch("/v1/model-providers"),
        new Promise<never>((_, reject) => setTimeout(() => reject(new Error("timeout")), 8000)),
      ]);
      const data = await resp.json();
      setCategories(data.categories || {});
    } catch (e) {
      console.error("Failed to load providers:", e);
    }
  }, []);

  const fetchDefaults = useCallback(async () => {
    try {
      const resp = await Promise.race([
        fetch("/v1/model-providers/user/defaults"),
        new Promise<never>((_, reject) => setTimeout(() => reject(new Error("timeout")), 8000)),
      ]);
      const data = await resp.json();
      setDefaults(data.defaults || {});
    } catch (e) {
      console.error("Failed to load defaults:", e);
    }
  }, []);

  useEffect(() => {
    const timeout = setTimeout(() => setLoading(false), 10000);
    Promise.all([fetchProviders(), fetchDefaults()]).finally(() => {
      clearTimeout(timeout);
      setLoading(false);
    });
    return () => clearTimeout(timeout);
  }, [fetchProviders, fetchDefaults]);

  const handleTestProvider = async (provider: Provider) => {
    const toastId = toast.loading(t("settings.models.testingConnection"));
    try {
      const resp = await fetch(`/v1/model-providers/${provider.id}/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: "", base_url: "" }),
      });
      const result: ConnectionTestResult = await resp.json();
      if (result.success) {
        toast.success(
          `${provider.name} ${t("settings.models.modal.connectedMs", { ms: result.latency_ms })}`,
          { id: toastId }
        );
      } else {
        toast.error(`${provider.name}: ${result.error}`, { id: toastId });
      }
    } catch {
      toast.error(t("settings.models.testRequestFailed"), { id: toastId });
    }
  };

  const handleSaveDefault = async (taskType: string, providerId: string, modelId: string) => {
    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const body: Record<string, any> = {};
      body[taskType] = { provider_id: providerId, model_id: modelId };
      const resp = await fetch("/v1/model-providers/user/defaults", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!resp.ok) throw new Error("Save failed");
      toast.success(t("settings.models.defaultUpdated"));
      await fetchDefaults();
    } catch (e: any) {
      toast.error(e.message || t("settings.models.saveFailed"));
    }
  };

  const categoryOrder = [
    { key: "cloud_cn", icon: "CN" },
    { key: "cloud_intl", icon: "GL" },
    { key: "local", icon: "LC" },
  ];

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-50 to-indigo-50 flex items-center justify-center">
        <div className="text-gray-500 text-lg">{t("settings.models.loading")}</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-indigo-50">
      <div className="container mx-auto px-4 py-8 max-w-6xl">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center space-x-4 mb-4">
            <button
              onClick={() => router.push("/dashboard")}
              className="flex items-center text-gray-600 hover:text-gray-900 transition-colors"
            >
              <svg
                className="w-5 h-5 mr-2"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M10 19l-7-7m0 0l7-7m-7 7h18"
                />
              </svg>
              {t("settings.models.backHome")}
            </button>
          </div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">{t("settings.models.title")}</h1>
          <p className="text-gray-600">{t("settings.models.subtitle")}</p>
        </div>

        {/* Tabs */}
        <div className="mb-6 border-b border-gray-200">
          <nav className="-mb-px flex space-x-8">
            <TabButton
              label={t("settings.models.tabProviders")}
              active={activeTab === "providers"}
              onClick={() => setActiveTab("providers")}
            />
            <TabButton
              label={t("settings.models.tabDefaults")}
              active={activeTab === "defaults"}
              onClick={() => setActiveTab("defaults")}
            />
          </nav>
        </div>

        {/* Content */}
        {activeTab === "providers" && (
          <div className="space-y-8">
            {categoryOrder.map(({ key, icon }) => {
              const cat = categories[key];
              if (!cat || cat.providers.length === 0) return null;
              return (
                <div key={key}>
                  <div className="flex items-center space-x-2 mb-4">
                    <span className="inline-flex items-center justify-center w-8 h-8 rounded bg-indigo-100 text-xs font-bold text-indigo-600">
                      {icon}
                    </span>
                    <h2 className="text-lg font-semibold text-gray-900">{cat.label}</h2>
                    <span className="text-sm text-gray-400">({cat.label_en})</span>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {cat.providers.map((provider) => (
                      <ProviderCard
                        key={provider.id}
                        provider={provider}
                        onConfigure={(p) => setConfiguring(p)}
                        onTest={handleTestProvider}
                      />
                    ))}
                  </div>
                </div>
              );
            })}

            {allProviders.length === 0 && (
              <div className="text-center py-12 text-gray-500">
                {t("settings.models.noProviders")}
              </div>
            )}
          </div>
        )}

        {activeTab === "defaults" && (
          <div className="space-y-4">
            <div className="bg-blue-50 rounded-lg p-4 mb-6">
              <p className="text-sm text-blue-700" style={{ whiteSpace: "pre-line" }}>
                {t("settings.models.defaults.hint")}
              </p>
            </div>

            <DefaultModelSelector
              taskType="chat"
              taskLabel={t("settings.models.taskTypes.chat.label")}
              taskDesc={t("settings.models.taskTypes.chat.desc")}
              allProviders={allProviders}
              currentDefault={defaults.chat}
              onSave={handleSaveDefault}
            />
            <DefaultModelSelector
              taskType="extraction"
              taskLabel={t("settings.models.taskTypes.extraction.label")}
              taskDesc={t("settings.models.taskTypes.extraction.desc")}
              allProviders={allProviders}
              currentDefault={defaults.extraction}
              onSave={handleSaveDefault}
            />
            <DefaultModelSelector
              taskType="embedding"
              taskLabel={t("settings.models.taskTypes.embedding.label")}
              taskDesc={t("settings.models.taskTypes.embedding.desc")}
              allProviders={allProviders}
              currentDefault={defaults.embedding}
              onSave={handleSaveDefault}
            />
          </div>
        )}

        {/* Config Modal */}
        {configuring && (
          <ProviderConfigModal
            provider={configuring}
            onClose={() => setConfiguring(null)}
            onSaved={() => {
              setConfiguring(null);
              fetchProviders();
            }}
            onDeleted={() => {
              setConfiguring(null);
              fetchProviders();
            }}
          />
        )}
      </div>
    </div>
  );
}
