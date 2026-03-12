"use client";

import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import { fetch } from "@/utils";

interface Permission {
  id: string;
  name: string;
  code: string;
  description?: string;
  category?: string;
}

interface Role {
  id: string;
  name: string;
}

export default function TenantPermissionsPanel() {
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [selectedRole, setSelectedRole] = useState<string>("");
  const [rolePermissions, setRolePermissions] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const { t } = useTranslation();

  useEffect(() => {
    fetchPermissions();
    fetchRoles();
  }, []);

  useEffect(() => {
    if (selectedRole) {
      fetchRolePermissions(selectedRole);
    }
  }, [selectedRole]);

  const fetchPermissions = async () => {
    try {
      const response = await fetch("/v1/permissions/function-permissions");
      const data = await response.json();
      setPermissions(data.permissions || []);
    } catch (error) {
      console.error("Failed to get permissions:", error);
      toast.error("Failed to get permissions");
    }
  };

  const fetchRoles = async () => {
    try {
      const response = await fetch("/v1/permissions/my-tenant/roles");
      const data = await response.json();
      setRoles(data.roles || []);
    } catch (error) {
      console.error("Failed to get roles:", error);
      toast.error("Failed to get roles");
    }
  };

  const fetchRolePermissions = async (roleId: string) => {
    setLoading(true);
    try {
      const response = await fetch(`/v1/permissions/roles/${roleId}/permissions`);
      const data = await response.json();
      const permissionIds = data.permissions?.map((p: Permission) => p.id) || [];
      setRolePermissions(new Set(permissionIds));
    } catch (error) {
      console.error("Failed to get role permissions:", error);
      toast.error("Failed to get role permissions");
    } finally {
      setLoading(false);
    }
  };

  const handleTogglePermission = async (permissionId: string, hasPermission: boolean) => {
    if (!selectedRole) {
      toast.error(t("tenantAdmin.permissions.selectRoleFirst"));
      return;
    }

    try {
      if (hasPermission) {
        await fetch(`/v1/permissions/roles/${selectedRole}/permissions/${permissionId}`, {
          method: "DELETE",
        });
        toast.success("Permission removed");
      } else {
        await fetch(`/v1/permissions/roles/${selectedRole}/permissions/${permissionId}`, {
          method: "POST",
        });
        toast.success("Permission added");
      }

      await fetchRolePermissions(selectedRole);
    } catch (error) {
      console.error("Update permission failed:", error);
      toast.error("Update permission failed");
    }
  };

  const groupedPermissions = permissions.reduce((acc, perm) => {
    const category = perm.category || "Other";
    if (!acc[category]) {
      acc[category] = [];
    }
    acc[category].push(perm);
    return acc;
  }, {} as Record<string, Permission[]>);

  return (
    <div className="space-y-6">
      <div className="bg-blue-50 p-4 rounded-lg">
        <h3 className="font-semibold text-blue-900 mb-2">{t("tenantAdmin.permissions.title")}</h3>
        <p className="text-sm text-blue-700">
          {t("tenantAdmin.permissions.description")}
        </p>
      </div>

      <div className="bg-white p-4 rounded-lg border border-gray-200">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          {t("tenantAdmin.permissions.selectRoleLabel")}
        </label>
        <select
          value={selectedRole}
          onChange={(e) => setSelectedRole(e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          <option value="">{t("tenantAdmin.permissions.selectRolePlaceholder")}</option>
          {roles.map((role) => (
            <option key={role.id} value={role.id}>
              {role.name}
            </option>
          ))}
        </select>
      </div>

      {selectedRole ? (
        loading ? (
          <div className="text-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mx-auto"></div>
            <p className="mt-2 text-gray-600">{t("tenantAdmin.permissions.loading")}</p>
          </div>
        ) : (
          <div className="space-y-4">
            {Object.keys(groupedPermissions).length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                {t("tenantAdmin.permissions.noPermissions")}
              </div>
            ) : (
              Object.entries(groupedPermissions).map(([category, perms]) => (
                <div key={category} className="bg-white p-4 rounded-lg border border-gray-200">
                  <h4 className="font-semibold text-gray-900 mb-3">{category}</h4>
                  <div className="space-y-2">
                    {perms.map((perm) => {
                      const hasPermission = rolePermissions.has(perm.id);
                      return (
                        <div
                          key={perm.id}
                          className="flex items-center justify-between p-3 bg-gray-50 rounded hover:bg-gray-100 transition-colors"
                        >
                          <div className="flex-1">
                            <div className="font-medium text-gray-900">{perm.name}</div>
                            {perm.description && (
                              <div className="text-sm text-gray-600 mt-1">{perm.description}</div>
                            )}
                            <div className="text-xs text-gray-400 mt-1">{t("tenantAdmin.permissions.permCode")} {perm.code}</div>
                          </div>
                          <label className="relative inline-flex items-center cursor-pointer">
                            <input
                              type="checkbox"
                              checked={hasPermission}
                              onChange={() => handleTogglePermission(perm.id, hasPermission)}
                              className="sr-only peer"
                            />
                            <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-indigo-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-indigo-600"></div>
                          </label>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))
            )}
          </div>
        )
      ) : (
        <div className="text-center py-8 text-gray-500">
          {t("tenantAdmin.permissions.selectRoleFirst")}
        </div>
      )}
    </div>
  );
}
