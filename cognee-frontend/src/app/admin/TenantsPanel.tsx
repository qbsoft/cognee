"use client";

import { useState, useEffect } from "react";
import toast from "react-hot-toast";
import { CTAButton, Input } from "@/ui/elements";
import { fetch } from "@/utils";
import TenantUsersModal from "./TenantUsersModal";
import TenantRolesModal from "./TenantRolesModal";

interface Tenant {
  id: string;
  name: string;
  tenant_code?: string;  // 租户编码
  expires_at?: string | null;  // 有效期
  created_at: string;
  owner_id: string;
}

export default function TenantsPanel() {
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
      console.error("获取租户列表失败:", error);
      toast.error("获取租户列表失败，请稍后重试");
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
      
      // 显示新创建的租户信息
      if (data.tenant_code) {
        const expiresDate = data.expires_at ? new Date(data.expires_at).toLocaleDateString("zh-CN") : "未设置";
        const adminInfo = data.admin_account 
          ? `

管理员账号：${data.admin_account.username}
管理员密码：${data.admin_account.password}

请妥善保管账号信息！`
          : "";
        
        toast.success(
          `租户创建成功！

租户名称：${newTenantName}
租户编码：${data.tenant_code}
有效期至：${expiresDate}${adminInfo}`,
          { duration: 6000 }
        );
      }

      setNewTenantName("");
      await fetchTenants();
    } catch (error) {
      console.error("创建租户失败:", error);
      toast.error("创建租户失败，请检查您是否为 super-admin 用户");
    } finally {
      setIsCreating(false);
    }
  };

  const handleCopyCode = async (code: string) => {
    try {
      await navigator.clipboard.writeText(code);
      setCopiedCode(code);
      toast.success("租户编码已复制到剪贴板");
      setTimeout(() => setCopiedCode(null), 2000);
    } catch (error) {
      console.error("复制失败:", error);
      toast.error("复制失败，请手动复制");
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
      
      toast.success(
        `租户有效期更新成功！\n\n租户名称：${data.tenant_name}\n有效期：${data.expires_at ? new Date(data.expires_at).toLocaleString("zh-CN") : "无限期"}`,
        { duration: 4000 }
      );
      
      setEditingExpiresFor(null);
      setExpiresDate("");
      await fetchTenants();
    } catch (error: any) {
      console.error("更新有效期失败:", error);
      toast.error(`更新有效期失败：${error.message || "请检查您是否为 super-admin 用户"}`);
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
        toast.success(
          `邀请链接已复制到剪贴板！

${fullUrl}

有效期至：${new Date(data.expires_at).toLocaleString("zh-CN")}`,
          { duration: 5000 }
        );
      }
    } catch (error) {
      console.error("生成邀请链接失败:", error);
      toast.error("生成邀请链接失败，请检查您的权限");
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
        <h3 className="text-lg font-semibold mb-4">创建新租户</h3>
        <div className="flex flex-row gap-3">
          <Input
            type="text"
            placeholder="输入租户名称"
            value={newTenantName}
            onChange={(e) => setNewTenantName(e.target.value)}
            className="flex-1"
          />
          <CTAButton onClick={handleCreateTenant} disabled={isCreating || !newTenantName.trim()}>
            {isCreating ? "创建中..." : "创建租户"}
          </CTAButton>
        </div>
        <p className="text-sm text-gray-600 mt-2">
          租户是组织的顶层容器，用于隔离不同组织的数据和用户。
          <strong>注意：只有 super-admin 用户才能创建租户。</strong>
        </p>
      </div>

      <div>
        <h3 className="text-lg font-semibold mb-4">现有租户</h3>
        {tenants.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            暂无租户，请创建第一个租户
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
                        <span className="text-sm text-gray-600">租户编码：</span>
                        <code className="px-2 py-1 bg-indigo-50 text-indigo-700 rounded font-mono text-sm tracking-wider">
                          {tenant.tenant_code}
                        </code>
                        <button
                          onClick={() => handleCopyCode(tenant.tenant_code!)}
                          className="text-xs text-indigo-600 hover:text-indigo-800"
                        >
                          {copiedCode === tenant.tenant_code ? "✓ 已复制" : "复制"}
                        </button>
                      </div>
                    )}
                    
                    <div className="text-sm text-gray-500 mt-1">ID: {tenant.id}</div>
                    <div className="text-sm text-gray-400 mt-1">
                      创建时间: {new Date(tenant.created_at).toLocaleString("zh-CN")}
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
                                alert("请选择有效期日期");
                                return;
                              }
                              // 转换为 ISO 8601 格式（设置为当天23:59:59）
                              const isoDate = `${expiresDate}T23:59:59Z`;
                              handleUpdateExpires(tenant.id, isoDate);
                            }}
                            className="text-xs px-2 py-1 bg-green-600 text-white rounded hover:bg-green-700"
                          >
                            保存
                          </button>
                          <button
                            onClick={() => {
                              setEditingExpiresFor(null);
                              setExpiresDate("");
                            }}
                            className="text-xs text-gray-600 hover:text-gray-800"
                          >
                            取消
                          </button>
                        </div>
                      ) : (
                        <div className="flex items-center gap-2">
                          <span className="text-sm text-gray-600">有效期：</span>
                          <span className={`text-sm font-medium ${
                            !tenant.expires_at ? "text-green-600" :
                            new Date(tenant.expires_at) < new Date() ? "text-red-600" :
                            "text-gray-700"
                          }`}>
                            {tenant.expires_at ? new Date(tenant.expires_at).toLocaleDateString("zh-CN") : "无限期"}
                            {tenant.expires_at && new Date(tenant.expires_at) < new Date() && " (已过期)"}
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
                            修改
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
                      {generatingInviteFor === tenant.id ? "生成中..." : "生成邀请链接"}
                    </CTAButton>
                    
                    <button
                      onClick={() => setSelectedTenantForUsers({ id: tenant.id, name: tenant.name })}
                      className="text-sm py-1 px-3 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
                    >
                      查看用户
                    </button>
                    
                    <button
                      onClick={() => setSelectedTenantForRoles({ id: tenant.id, name: tenant.name })}
                      className="text-sm py-1 px-3 bg-green-600 text-white rounded hover:bg-green-700 transition-colors"
                    >
                      查看角色
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
