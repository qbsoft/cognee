"use client";

import { useState, useEffect } from "react";
import { CTAButton, Input } from "@/ui/elements";
import { fetch } from "@/utils";
import { useTranslation } from "react-i18next";

interface Role {
  id: string;
  name: string;
  tenant_id: string;
  created_at: string;
}

export default function RolesPanel() {
  const { t } = useTranslation();
  const [roles, setRoles] = useState<Role[]>([]);
  const [newRoleName, setNewRoleName] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  const fetchRoles = async () => {
    try {
      // 注意: 后端需要添加 GET /v1/permissions/roles API
      const response = await fetch("/v1/permissions/roles");
      const data = await response.json();
      setRoles(data.roles || []);
    } catch (error) {
      console.error("获取角色列表失败:", error);
    }
  };

  useEffect(() => {
    fetchRoles();
  }, []);

  const handleCreateRole = async () => {
    if (!newRoleName.trim()) return;

    setIsCreating(true);
    try {
      const formData = new URLSearchParams();
      formData.append("role_name", newRoleName);

      await fetch("/v1/permissions/roles", {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: formData.toString(),
      });

      setNewRoleName("");
      await fetchRoles();
    } catch (error) {
      console.error("创建角色失败:", error);
      alert(t("admin.roles.createError"));
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-gray-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-4">{t("admin.roles.createTitle")}</h3>
        <div className="flex flex-row gap-3">
          <Input
            type="text"
            placeholder={t("admin.roles.rolePlaceholder")}
            value={newRoleName}
            onChange={(e) => setNewRoleName(e.target.value)}
            className="flex-1"
          />
          <CTAButton onClick={handleCreateRole} disabled={isCreating || !newRoleName.trim()}>
            {isCreating ? t("admin.roles.creating") : t("admin.roles.createButton")}
          </CTAButton>
        </div>
        <p className="text-sm text-gray-600 mt-2">
          {t("admin.roles.roleNote")}
        </p>
      </div>

      <div>
        <h3 className="text-lg font-semibold mb-4">{t("admin.roles.existingTitle")}</h3>
        {roles.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            {t("admin.roles.noRoles")}
          </div>
        ) : (
          <div className="space-y-2">
            {roles.map((role) => (
              <div
                key={role.id}
                className="p-4 border border-gray-200 rounded-lg hover:border-indigo-600 transition-colors"
              >
                <div className="flex flex-row justify-between items-center">
                  <div>
                    <div className="font-semibold">{role.name}</div>
                    <div className="text-sm text-gray-500">
                      ID: {role.id} | {t("admin.roles.tenant")} {role.tenant_id}
                    </div>
                  </div>
                  <div className="text-sm text-gray-400">
                    {t("admin.tenants.createdAt")} {new Date(role.created_at).toLocaleString("zh-CN")}
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
