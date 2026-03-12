"use client";

import { useState, useEffect } from "react";
import toast from "react-hot-toast";
import { CTAButton, Input } from "@/ui/elements";
import { fetch } from "@/utils";
import TenantUsersModal from "./TenantUsersModal";
import TenantRolesModal from "./TenantRolesModal";
import { useTranslation } from "react-i18next";

interface Tenant {
  id: string;
  name: string;
  tenant_code?: string;  // 租户编码
  expires_at?: string | null;  // 有效期
  created_at: string;
  owner_id: string;
}

export default function TenantsPanel() {
  const { t } = useTranslation();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [newTenantName, setNewTenantName] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [copiedCode, setCopiedCode] = useState<string | null>(null);
  const [generatingInviteFor, setGeneratingInviteFor] = useState<string | null>(null);
  const [editingExpiresFor, setEditingExpiresFor] = useState<string | null>(null);
  const [expiresDate, setExpiresDate] = useState<string>("");

  // Modal states
  const [selectedTenantForUsers, setSelectedTenantForUsers] = useState<{ id: string; name: string } | null>(null);
  const [selectedTenantForRoles, setSelectedTenantForRoles] = useState<{ id: string; name: string } | null>(null);

  const fetchTenants = async () => {
    try {
      // 注意: 后端需要添加 GET /v1/permissions/tenants API
      const response = await fetch("/v1/permissions/tenants");
      const data = await response.json();
      setTenants(data.tenants || []);
    } catch (error) {
      console.error("Failed to fetch tenant list:", error);
      toast.error(t("admin.tenants.fetchError"));
    }
  };

  useEffect(() => {
    fetchTenants();
  }, []);

  const handleCreateTenant = async () => {
    if (!newTenantName.trim()) return;

    setIsCreating(true);
    try {
      // tenant_name 作为 query 参数传递
      const response = await fetch(`/v1/permissions/tenants?tenant_name=${encodeURIComponent(newTenantName)}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      });

      const data = await response.json();

      // Show newly created tenant info
      if (data.tenant_code) {
        toast.success(t("admin.tenants.createButton") + " OK", { duration: 6000 });
      }

      setNewTenantName("");
      await fetchTenants();
    } catch (error) {
      console.error("Failed to create tenant:", error);
      toast.error(t("admin.tenants.createError"));
    } finally {
      setIsCreating(false);
    }
  };

  const handleCopyCode = async (code: string) => {
    try {
      await navigator.clipboard.writeText(code);
      setCopiedCode(code);
      toast.success(t("admin.tenants.copySuccess"));
      setTimeout(() => setCopiedCode(null), 2000);
    } catch (error) {
      console.error("Copy failed:", error);
      toast.error(t("admin.tenants.copyError"));
    }
  };

  const handleUpdateExpires = async (tenantId: string, expiresAt: string | null) => {
    try {
      const response = await fetch(`/v1/permissions/tenants/${tenantId}/expires`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ expires_at: expiresAt }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      const data = await response.json();

      toast.success(t("admin.tenants.updateSuccess"), { duration: 4000 });

      setEditingExpiresFor(null);
      setExpiresDate("");
      await fetchTenants();
    } catch (error: any) {
      console.error("Failed to update validity:", error);
      toast.error(t("admin.tenants.updateError"));
    }
  };

  const handleGenerateInvite = async (tenantId: string) => {
    setGeneratingInviteFor(tenantId);
    try {
      const response = await fetch(`/v1/permissions/tenants/${tenantId}/invite`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      });

      const data = await response.json();

      if (data.invite_url) {
        const fullUrl = `${window.location.origin}${data.invite_url}`;
        await navigator.clipboard.writeText(fullUrl);
        toast.success(t("admin.tenants.inviteSuccess"), { duration: 5000 });
      }
    } catch (error) {
      console.error("Failed to generate invite link:", error);
      toast.error(t("admin.tenants.inviteError"));
    } finally {
      setGeneratingInviteFor(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* 用户列表模态框 */}
      {selectedTenantForUsers && (
        <TenantUsersModal
          tenantId={selectedTenantForUsers.id}
          tenantName={selectedTenantForUsers.name}
          onClose={() => setSelectedTenantForUsers(null)}
        />
      )}

      {/* 角色列表模态框 */}
      {selectedTenantForRoles && (
        <TenantRolesModal
          tenantId={selectedTenantForRoles.id}
          tenantName={selectedTenantForRoles.name}
          onClose={() => setSelectedTenantForRoles(null)}
        />
      )}
      <div className="bg-gray-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-4">{t("admin.tenants.createTitle")}</h3>
        <div className="flex flex-row gap-3">
          <Input
            type="text"
            placeholder={t("admin.tenants.namePlaceholder")}
            value={newTenantName}
            onChange={(e) => setNewTenantName(e.target.value)}
            className="flex-1"
          />
          <CTAButton onClick={handleCreateTenant} disabled={isCreating || !newTenantName.trim()}>
            {isCreating ? t("admin.tenants.creating") : t("admin.tenants.createButton")}
          </CTAButton>
        </div>
        <p className="text-sm text-gray-600 mt-2">
          {t("admin.tenants.note")}
        </p>
      </div>

      <div>
        <h3 className="text-lg font-semibold mb-4">{t("admin.tenants.existingTitle")}</h3>
        {tenants.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            {t("admin.tenants.noTenants")}
          </div>
        ) : (
          <div className="space-y-2">
            {tenants.map((tenant) => (
              <div
                key={tenant.id}
                className="p-4 border border-gray-200 rounded-lg hover:border-indigo-600 transition-colors"
              >
                <div className="flex flex-row justify-between items-start">
                  <div className="flex-1">
                    <div className="font-semibold text-lg">{tenant.name}</div>

                    {/* 租户编码 */}
                    {tenant.tenant_code && (
                      <div className="mt-2 flex items-center gap-2">
                        <span className="text-sm text-gray-600">{t("admin.tenants.tenantCode")}</span>
                        <code className="px-2 py-1 bg-indigo-50 text-indigo-700 rounded font-mono text-sm tracking-wider">
                          {tenant.tenant_code}
                        </code>
                        <button
                          onClick={() => handleCopyCode(tenant.tenant_code!)}
                          className="text-xs text-indigo-600 hover:text-indigo-800"
                        >
                          {copiedCode === tenant.tenant_code ? t("admin.tenants.copied") : t("admin.tenants.copy")}
                        </button>
                      </div>
                    )}

                    <div className="text-sm text-gray-500 mt-1">ID: {tenant.id}</div>
                    <div className="text-sm text-gray-400 mt-1">
                      {t("admin.tenants.createdAt")} {new Date(tenant.created_at).toLocaleString()}
                    </div>

                    {/* 有效期 */}
                    <div className="mt-2">
                      {editingExpiresFor === tenant.id ? (
                        <div className="flex items-center gap-2">
                          <Input
                            type="date"
                            value={expiresDate}
                            onChange={(e) => setExpiresDate(e.target.value)}
                            className="text-sm"
                          />
                          <button
                            onClick={() => {
                              if (!expiresDate) {
                                alert(t("admin.tenants.selectDate"));
                                return;
                              }
                              // 转换为 ISO 8601 格式（设置为当天23:59:59）
                              const isoDate = `${expiresDate}T23:59:59Z`;
                              handleUpdateExpires(tenant.id, isoDate);
                            }}
                            className="text-xs px-2 py-1 bg-green-600 text-white rounded hover:bg-green-700"
                          >
                            {t("admin.tenants.save")}
                          </button>
                          <button
                            onClick={() => {
                              setEditingExpiresFor(null);
                              setExpiresDate("");
                            }}
                            className="text-xs text-gray-600 hover:text-gray-800"
                          >
                            {t("admin.tenants.cancel")}
                          </button>
                        </div>
                      ) : (
                        <div className="flex items-center gap-2">
                          <span className="text-sm text-gray-600">{t("admin.tenants.validity")}</span>
                          <span className={`text-sm font-medium ${
                            !tenant.expires_at ? "text-green-600" :
                            new Date(tenant.expires_at) < new Date() ? "text-red-600" :
                            "text-gray-700"
                          }`}>
                            {tenant.expires_at ? new Date(tenant.expires_at).toLocaleDateString() : t("admin.tenants.unlimited")}
                            {tenant.expires_at && new Date(tenant.expires_at) < new Date() && ` ${t("admin.tenants.expired")}`}
                          </span>
                          <button
                            onClick={() => {
                              setEditingExpiresFor(tenant.id);
                              if (tenant.expires_at) {
                                // 转换为 date input 格式 (YYYY-MM-DD)
                                const date = new Date(tenant.expires_at);
                                const year = date.getFullYear();
                                const month = String(date.getMonth() + 1).padStart(2, '0');
                                const day = String(date.getDate()).padStart(2, '0');
                                setExpiresDate(`${year}-${month}-${day}`);
                              } else {
                                // 默认设置为15天后
                                const futureDate = new Date();
                                futureDate.setDate(futureDate.getDate() + 15);
                                const year = futureDate.getFullYear();
                                const month = String(futureDate.getMonth() + 1).padStart(2, '0');
                                const day = String(futureDate.getDate()).padStart(2, '0');
                                setExpiresDate(`${year}-${month}-${day}`);
                              }
                            }}
                            className="text-xs text-indigo-600 hover:text-indigo-800"
                          >
                            {t("admin.tenants.modify")}
                          </button>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* 操作按钮 */}
                  <div className="flex flex-col gap-2">
                    <CTAButton
                      onClick={() => handleGenerateInvite(tenant.id)}
                      disabled={generatingInviteFor === tenant.id}
                      className="text-sm py-1 px-3"
                    >
                      {generatingInviteFor === tenant.id ? t("admin.tenants.generating") : t("admin.tenants.generateInvite")}
                    </CTAButton>

                    <button
                      onClick={() => setSelectedTenantForUsers({ id: tenant.id, name: tenant.name })}
                      className="text-sm py-1 px-3 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
                    >
                      {t("admin.tenants.viewUsers")}
                    </button>

                    <button
                      onClick={() => setSelectedTenantForRoles({ id: tenant.id, name: tenant.name })}
                      className="text-sm py-1 px-3 bg-green-600 text-white rounded hover:bg-green-700 transition-colors"
                    >
                      {t("admin.tenants.viewRoles")}
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
