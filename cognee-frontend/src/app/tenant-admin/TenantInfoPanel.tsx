"use client";

import { useState, useEffect } from "react";
import { fetch } from "@/utils";

interface TenantInfo {
  id: string;
  name: string;
  tenant_code: string;
  expires_at: string | null;
  created_at: string;
}

export default function TenantInfoPanel() {
  const [tenantInfo, setTenantInfo] = useState<TenantInfo | null>(null);
  const [inviteUrl, setInviteUrl] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [copiedCode, setCopiedCode] = useState(false);
  const [copiedUrl, setCopiedUrl] = useState(false);

  useEffect(() => {
    fetchTenantInfo();
  }, []);

  const fetchTenantInfo = async () => {
    try {
      setLoading(true);
      // 获取当前用户的租户信息
      const response = await fetch("/v1/permissions/my-tenant");
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      
      if (!data.tenant) {
        throw new Error("返回数据中没有租户信息");
      }
      
      setTenantInfo(data.tenant);
    } catch (error) {
      console.error("获取租户信息失败:", error);
      alert(`获取租户信息失败: ${error instanceof Error ? error.message : '未知错误'}`);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateInvite = async () => {
    if (!tenantInfo) return;
    
    try {
      const response = await fetch(`/v1/permissions/tenants/${tenantInfo.id}/invite`, {
        method: "POST",
      });
      const data = await response.json();
      
      if (data.invite_url) {
        const fullUrl = `${window.location.origin}${data.invite_url}`;
        setInviteUrl(fullUrl);
        alert(`邀请链接生成成功！\n\n有效期至：${new Date(data.expires_at).toLocaleString("zh-CN")}`);
      }
    } catch (error) {
      console.error("生成邀请链接失败:", error);
      alert("生成邀请链接失败");
    }
  };

  const handleCopy = async (text: string, type: "code" | "url") => {
    try {
      await navigator.clipboard.writeText(text);
      if (type === "code") {
        setCopiedCode(true);
        setTimeout(() => setCopiedCode(false), 2000);
      } else {
        setCopiedUrl(true);
        setTimeout(() => setCopiedUrl(false), 2000);
      }
    } catch (error) {
      console.error("复制失败:", error);
    }
  };

  if (loading) {
    return <div className="text-center py-8 text-gray-500">加载中...</div>;
  }

  if (!tenantInfo) {
    return <div className="text-center py-8 text-red-500">无法获取租户信息</div>;
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-gray-900">租户信息（只读）</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* 租户名称 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">租户名称</label>
          <div className="px-4 py-3 bg-gray-50 rounded-md text-gray-900">
            {tenantInfo.name}
          </div>
        </div>

        {/* 租户编码 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">租户编码</label>
          <div className="flex items-center gap-2">
            <code className="flex-1 px-4 py-3 bg-indigo-50 text-indigo-700 rounded-md font-mono tracking-wider">
              {tenantInfo.tenant_code}
            </code>
            <button
              onClick={() => handleCopy(tenantInfo.tenant_code, "code")}
              className="px-4 py-3 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 transition-colors"
            >
              {copiedCode ? "✓ 已复制" : "复制"}
            </button>
          </div>
          <p className="text-xs text-gray-500 mt-1">用户可通过此编码注册加入租户</p>
        </div>

        {/* 创建时间 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">创建时间</label>
          <div className="px-4 py-3 bg-gray-50 rounded-md text-gray-900">
            {new Date(tenantInfo.created_at).toLocaleString("zh-CN")}
          </div>
        </div>

        {/* 有效期 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">有效期</label>
          <div className={`px-4 py-3 rounded-md font-medium ${
            !tenantInfo.expires_at ? "bg-green-50 text-green-700" :
            new Date(tenantInfo.expires_at) < new Date() ? "bg-red-50 text-red-700" :
            "bg-gray-50 text-gray-900"
          }`}>
            {tenantInfo.expires_at 
              ? `${new Date(tenantInfo.expires_at).toLocaleDateString("zh-CN")}${
                  new Date(tenantInfo.expires_at) < new Date() ? " (已过期)" : ""
                }`
              : "无限期"
            }
          </div>
        </div>
      </div>

      {/* 邀请链接 */}
      <div className="pt-6 border-t border-gray-200">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">注册邀请链接</h3>
        
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <button
              onClick={handleGenerateInvite}
              className="px-6 py-3 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 transition-colors"
            >
              生成新的邀请链接
            </button>
            {inviteUrl && (
              <span className="text-sm text-green-600">✓ 链接已生成</span>
            )}
          </div>

          {inviteUrl && (
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={inviteUrl}
                readOnly
                className="flex-1 px-4 py-3 bg-gray-50 border border-gray-300 rounded-md text-gray-700 text-sm"
              />
              <button
                onClick={() => handleCopy(inviteUrl, "url")}
                className="px-4 py-3 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 transition-colors"
              >
                {copiedUrl ? "✓ 已复制" : "复制链接"}
              </button>
            </div>
          )}

          <p className="text-sm text-gray-500">
            邀请链接有效期为 24 小时，用户通过链接注册将自动加入本租户。
          </p>
        </div>
      </div>
    </div>
  );
}
