"use client";

import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
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
  const { t } = useTranslation();

  useEffect(() => {
    fetchTenantInfo();
  }, []);

  const fetchTenantInfo = async () => {
    try {
      setLoading(true);
      const response = await fetch("/v1/permissions/my-tenant");

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      if (!data.tenant) {
        throw new Error("No tenant info in response");
      }

      setTenantInfo(data.tenant);
    } catch (error) {
      console.error("Failed to get tenant info:", error);
      alert(`Failed to get tenant info: ${error instanceof Error ? error.message : 'Unknown error'}`);
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
        alert(`Invite link generated!\n\nExpires at: ${new Date(data.expires_at).toLocaleString()}`);
      }
    } catch (error) {
      console.error("Failed to generate invite link:", error);
      alert("Failed to generate invite link");
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
      console.error("Copy failed:", error);
    }
  };

  if (loading) {
    return <div className="text-center py-8 text-gray-500">{t("tenantAdmin.info.loading")}</div>;
  }

  if (!tenantInfo) {
    return <div className="text-center py-8 text-red-500">{t("tenantAdmin.info.error")}</div>;
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-gray-900">{t("tenantAdmin.info.title")}</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">{t("tenantAdmin.info.tenantName")}</label>
          <div className="px-4 py-3 bg-gray-50 rounded-md text-gray-900">
            {tenantInfo.name}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">{t("tenantAdmin.info.tenantCode")}</label>
          <div className="flex items-center gap-2">
            <code className="flex-1 px-4 py-3 bg-indigo-50 text-indigo-700 rounded-md font-mono tracking-wider">
              {tenantInfo.tenant_code}
            </code>
            <button
              onClick={() => handleCopy(tenantInfo.tenant_code, "code")}
              className="px-4 py-3 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 transition-colors"
            >
              {copiedCode ? t("tenantAdmin.info.copied") : t("common.copy")}
            </button>
          </div>
          <p className="text-xs text-gray-500 mt-1">{t("tenantAdmin.info.tenantCodeHint")}</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">{t("tenantAdmin.info.createdAt")}</label>
          <div className="px-4 py-3 bg-gray-50 rounded-md text-gray-900">
            {new Date(tenantInfo.created_at).toLocaleString()}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">{t("tenantAdmin.info.validity")}</label>
          <div className={`px-4 py-3 rounded-md font-medium ${
            !tenantInfo.expires_at ? "bg-green-50 text-green-700" :
            new Date(tenantInfo.expires_at) < new Date() ? "bg-red-50 text-red-700" :
            "bg-gray-50 text-gray-900"
          }`}>
            {tenantInfo.expires_at
              ? `${new Date(tenantInfo.expires_at).toLocaleDateString()}${
                  new Date(tenantInfo.expires_at) < new Date() ? ` ${t("tenantAdmin.info.expired")}` : ""
                }`
              : t("tenantAdmin.info.unlimited")
            }
          </div>
        </div>
      </div>

      <div className="pt-6 border-t border-gray-200">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">{t("tenantAdmin.info.inviteTitle")}</h3>

        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <button
              onClick={handleGenerateInvite}
              className="px-6 py-3 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 transition-colors"
            >
              {t("tenantAdmin.info.generateInvite")}
            </button>
            {inviteUrl && (
              <span className="text-sm text-green-600">{t("tenantAdmin.info.linkGenerated")}</span>
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
                {copiedUrl ? t("tenantAdmin.info.copied") : t("tenantAdmin.info.copyLink")}
              </button>
            </div>
          )}

          <p className="text-sm text-gray-500">
            {t("tenantAdmin.info.inviteNote")}
          </p>
        </div>
      </div>
    </div>
  );
}
