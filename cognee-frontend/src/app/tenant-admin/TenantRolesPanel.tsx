"use client";

import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import { fetch } from "@/utils";

interface Role {
  id: string;
  name: string;
  description?: string;
  created_at: string;
  user_count?: number;
}

export default function TenantRolesPanel() {
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [selectedRole, setSelectedRole] = useState<Role | null>(null);
  const [newRoleName, setNewRoleName] = useState("");
  const [newRoleDescription, setNewRoleDescription] = useState("");
  const { t } = useTranslation();

  useEffect(() => {
    fetchRoles();
  }, []);

  const fetchRoles = async () => {
    try {
      setLoading(true);
      const response = await fetch("/v1/permissions/my-tenant/roles");
      const data = await response.json();
      setRoles(data.roles || []);
    } catch (error) {
      console.error("Failed to get roles:", error);
      toast.error("Failed to get roles");
    } finally {
      setLoading(false);
    }
  };

  const handleCreateRole = async () => {
    if (!newRoleName.trim()) {
      toast.error(t("tenantAdmin.roles.roleNameLabel"));
      return;
    }

    try {
      const response = await fetch("/v1/permissions/my-tenant/roles", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newRoleName,
          description: newRoleDescription,
        }),
      });

      if (response.ok) {
        toast.success(t("tenantAdmin.roles.create") + " OK");
        setShowCreateDialog(false);
        setNewRoleName("");
        setNewRoleDescription("");
        await fetchRoles();
      } else {
        const data = await response.json();
        toast.error(data.detail || "Create role failed");
      }
    } catch (error) {
      console.error("Create role failed:", error);
      toast.error("Create role failed");
    }
  };

  const handleEditRole = async () => {
    if (!selectedRole) return;

    try {
      const response = await fetch(`/v1/permissions/roles/${selectedRole.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newRoleName,
          description: newRoleDescription,
        }),
      });

      if (response.ok) {
        toast.success(t("tenantAdmin.roles.save") + " OK");
        setShowEditDialog(false);
        setSelectedRole(null);
        setNewRoleName("");
        setNewRoleDescription("");
        await fetchRoles();
      } else {
        toast.error("Update role failed");
      }
    } catch (error) {
      console.error("Update role failed:", error);
      toast.error("Update role failed");
    }
  };

  const handleDeleteRole = async (roleId: string, roleName: string) => {
    if (!confirm(`Delete role "${roleName}"? This cannot be undone.`)) {
      return;
    }

    try {
      const response = await fetch(`/v1/permissions/roles/${roleId}`, {
        method: "DELETE",
      });

      if (response.ok) {
        toast.success(t("tenantAdmin.roles.delete") + " OK");
        await fetchRoles();
      } else {
        const data = await response.json();
        toast.error(data.detail || "Delete role failed");
      }
    } catch (error) {
      console.error("Delete role failed:", error);
      toast.error("Delete role failed");
    }
  };

  const openEditDialog = (role: Role) => {
    setSelectedRole(role);
    setNewRoleName(role.name);
    setNewRoleDescription(role.description || "");
    setShowEditDialog(true);
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
        <p className="mt-4 text-gray-500">{t("common.loading")}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-semibold text-gray-900">{t("tenantAdmin.roles.title")}</h2>
        <button
          onClick={() => setShowCreateDialog(true)}
          className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
        >
          {t("tenantAdmin.roles.createRole")}
        </button>
      </div>

      {roles.length === 0 ? (
        <div className="text-center py-8 text-gray-500">{t("tenantAdmin.roles.noRoles")}</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {roles.map((role) => (
            <div
              key={role.id}
              className="border border-gray-200 rounded-lg p-4 hover:border-indigo-600 transition-colors"
            >
              <div className="flex justify-between items-start mb-3">
                <div>
                  <h3 className="font-semibold text-gray-900">{role.name}</h3>
                  {role.description && (
                    <p className="text-sm text-gray-600 mt-1">{role.description}</p>
                  )}
                </div>
              </div>

              <div className="text-xs text-gray-500 mb-3">
                {t("tenantAdmin.roles.createdAt")} {new Date(role.created_at).toLocaleDateString()}
              </div>

              {role.user_count !== undefined && (
                <div className="text-sm text-gray-600 mb-3">
                  {t("tenantAdmin.roles.usersCount", { count: role.user_count })}
                </div>
              )}

              <div className="flex gap-2">
                <button
                  onClick={() => openEditDialog(role)}
                  className="flex-1 text-sm text-indigo-600 hover:text-indigo-800"
                >
                  {t("tenantAdmin.roles.edit")}
                </button>
                <button
                  onClick={() => handleDeleteRole(role.id, role.name)}
                  className="flex-1 text-sm text-red-600 hover:text-red-800"
                >
                  {t("tenantAdmin.roles.delete")}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {showCreateDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold mb-4">{t("tenantAdmin.roles.createTitle")}</h3>

            <div className="space-y-4 mb-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  {t("tenantAdmin.roles.roleNameLabel")}
                </label>
                <input
                  type="text"
                  value={newRoleName}
                  onChange={(e) => setNewRoleName(e.target.value)}
                  placeholder={t("tenantAdmin.roles.roleNamePlaceholder")}
                  className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  {t("tenantAdmin.roles.descLabel")}
                </label>
                <textarea
                  value={newRoleDescription}
                  onChange={(e) => setNewRoleDescription(e.target.value)}
                  placeholder={t("tenantAdmin.roles.descPlaceholder")}
                  rows={3}
                  className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>
            </div>

            <div className="flex justify-end gap-3">
              <button
                onClick={() => {
                  setShowCreateDialog(false);
                  setNewRoleName("");
                  setNewRoleDescription("");
                }}
                className="px-4 py-2 text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200"
              >
                {t("tenantAdmin.roles.cancel")}
              </button>
              <button
                onClick={handleCreateRole}
                className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
              >
                {t("tenantAdmin.roles.create")}
              </button>
            </div>
          </div>
        </div>
      )}

      {showEditDialog && selectedRole && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold mb-4">{t("tenantAdmin.roles.editTitle")}</h3>

            <div className="space-y-4 mb-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  {t("tenantAdmin.roles.roleNameLabel")}
                </label>
                <input
                  type="text"
                  value={newRoleName}
                  onChange={(e) => setNewRoleName(e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  {t("tenantAdmin.roles.descLabel")}
                </label>
                <textarea
                  value={newRoleDescription}
                  onChange={(e) => setNewRoleDescription(e.target.value)}
                  rows={3}
                  className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>
            </div>

            <div className="flex justify-end gap-3">
              <button
                onClick={() => {
                  setShowEditDialog(false);
                  setSelectedRole(null);
                  setNewRoleName("");
                  setNewRoleDescription("");
                }}
                className="px-4 py-2 text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200"
              >
                {t("tenantAdmin.roles.cancel")}
              </button>
              <button
                onClick={handleEditRole}
                className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
              >
                {t("tenantAdmin.roles.save")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
