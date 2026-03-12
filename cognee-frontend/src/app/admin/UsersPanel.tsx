"use client";

import { useState, useEffect } from "react";
import { CTAButton, Input } from "@/ui/elements";
import { fetch } from "@/utils";
import { useTranslation } from "react-i18next";

interface User {
  id: string;
  email: string;
  is_active: boolean;
  is_verified: boolean;
  tenant_id: string | null;
}

export default function UsersPanel() {
  const { t } = useTranslation();
  const [users, setUsers] = useState<User[]>([]);
  const [newUserEmail, setNewUserEmail] = useState("");
  const [newUserPassword, setNewUserPassword] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  const fetchUsers = async () => {
    try {
      // 注意: 后端需要添加 GET /v1/users API
      const response = await fetch("/v1/users");
      const data = await response.json();
      setUsers(data.users || []);
    } catch (error) {
      console.error("获取用户列表失败:", error);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleCreateUser = async () => {
    if (!newUserEmail.trim() || !newUserPassword.trim()) return;

    setIsCreating(true);
    try {
      await fetch("/v1/auth/register", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: newUserEmail,
          password: newUserPassword,
        }),
      });

      setNewUserEmail("");
      setNewUserPassword("");
      await fetchUsers();
    } catch (error) {
      console.error("Create user failed:", error);
      alert(t("admin.users.createError"));
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-gray-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-4">{t("admin.users.createTitle")}</h3>
        <div className="space-y-3">
          <Input
            type="email"
            placeholder={t("admin.users.emailPlaceholder")}
            value={newUserEmail}
            onChange={(e) => setNewUserEmail(e.target.value)}
          />
          <Input
            type="password"
            placeholder={t("admin.users.passwordPlaceholder")}
            value={newUserPassword}
            onChange={(e) => setNewUserPassword(e.target.value)}
          />
          <CTAButton
            onClick={handleCreateUser}
            disabled={isCreating || !newUserEmail.trim() || !newUserPassword.trim()}
            className="w-full"
          >
            {isCreating ? t("admin.users.creating") : t("admin.users.createButton")}
          </CTAButton>
        </div>
        <p className="text-sm text-gray-600 mt-2">
          {t("admin.users.userNote")}
        </p>
      </div>

      <div>
        <h3 className="text-lg font-semibold mb-4">{t("admin.users.existingTitle")}</h3>
        {users.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            {t("admin.users.loadingUsers")}
          </div>
        ) : (
          <div className="space-y-2">
            {users.map((user) => (
              <div
                key={user.id}
                className="p-4 border border-gray-200 rounded-lg hover:border-indigo-600 transition-colors"
              >
                <div className="flex flex-row justify-between items-center">
                  <div>
                    <div className="font-semibold">{user.email}</div>
                    <div className="text-sm text-gray-500">
                      ID: {user.id}
                      {user.tenant_id && ` | ${t("admin.users.tenantId")} ${user.tenant_id}`}
                    </div>
                  </div>
                  <div className="flex flex-row gap-2">
                    <span
                      className={`px-2 py-1 rounded text-xs ${
                        user.is_active
                          ? "bg-green-100 text-green-800"
                          : "bg-red-100 text-red-800"
                      }`}
                    >
                      {user.is_active ? t("admin.users.active") : t("admin.users.inactive")}
                    </span>
                    <span
                      className={`px-2 py-1 rounded text-xs ${
                        user.is_verified
                          ? "bg-blue-100 text-blue-800"
                          : "bg-gray-100 text-gray-800"
                      }`}
                    >
                      {user.is_verified ? t("admin.users.verified") : t("admin.users.unverified")}
                    </span>
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
