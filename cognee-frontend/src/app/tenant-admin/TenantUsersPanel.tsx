"use client";

import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import { fetch } from "@/utils";

interface User {
  id: string;
  email: string;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  roles?: string[];
}

interface Role {
  id: string;
  name: string;
}

export default function TenantUsersPanel() {
  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [showRoleDialog, setShowRoleDialog] = useState(false);
  const [selectedRoles, setSelectedRoles] = useState<string[]>([]);
  const { t } = useTranslation();

  useEffect(() => {
    fetchUsers();
    fetchRoles();
  }, []);

  const fetchUsers = async () => {
    try {
      setLoading(true);
      const response = await fetch("/v1/permissions/my-tenant/users");
      const data = await response.json();
      setUsers(data.users || []);
    } catch (error) {
      console.error("Failed to get users:", error);
      toast.error(t("tenantAdmin.users.title") + " - error");
    } finally {
      setLoading(false);
    }
  };

  const fetchRoles = async () => {
    try {
      const response = await fetch("/v1/permissions/my-tenant/roles");
      const data = await response.json();
      setRoles(data.roles || []);
    } catch (error) {
      console.error("Failed to get roles:", error);
    }
  };

  const handleAssignRoles = (user: User) => {
    setSelectedUser(user);
    setSelectedRoles(user.roles || []);
    setShowRoleDialog(true);
  };

  const handleSaveRoles = async () => {
    if (!selectedUser) return;

    try {
      const response = await fetch(`/v1/permissions/users/${selectedUser.id}/roles`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role_names: selectedRoles }),
      });

      if (response.ok) {
        toast.success(t("tenantAdmin.users.assignRoles") + " OK");
        setShowRoleDialog(false);
        await fetchUsers();
      } else {
        toast.error("Role assignment failed");
      }
    } catch (error) {
      console.error("Save roles failed:", error);
      toast.error("Save roles failed");
    }
  };

  const toggleRole = (roleName: string) => {
    setSelectedRoles((prev) =>
      prev.includes(roleName)
        ? prev.filter((r) => r !== roleName)
        : [...prev, roleName]
    );
  };

  const handleToggleActive = async (user: User) => {
    const action = user.is_active ? t("tenantAdmin.users.disable") : t("tenantAdmin.users.enable");
    if (!confirm(`${action} user ${user.email}?`)) {
      return;
    }

    try {
      const response = await fetch(`/v1/permissions/users/${user.id}/active`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: !user.is_active }),
      });

      if (response.ok) {
        toast.success(`${action} OK`);
        await fetchUsers();
      } else {
        const data = await response.json();
        toast.error(data.detail || `${action} failed`);
      }
    } catch (error) {
      console.error(`${action} failed:`, error);
      toast.error(`${action} failed`);
    }
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
        <h2 className="text-xl font-semibold text-gray-900">{t("tenantAdmin.users.title")}</h2>
        <span className="text-sm text-gray-500">{t("tenantAdmin.users.totalUsers", { count: users.length })}</span>
      </div>

      {users.length === 0 ? (
        <div className="text-center py-8 text-gray-500">{t("tenantAdmin.users.noUsers")}</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t("tenantAdmin.users.colEmail")}
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t("tenantAdmin.users.colRoles")}
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t("tenantAdmin.users.colStatus")}
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t("tenantAdmin.users.colCreatedAt")}
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t("tenantAdmin.users.colActions")}
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {users.map((user) => (
                <tr key={user.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {user.email}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                    {user.roles && user.roles.length > 0
                      ? user.roles.join(", ")
                      : t("tenantAdmin.users.noRole")}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span
                      className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${
                        user.is_active
                          ? "bg-green-100 text-green-800"
                          : "bg-red-100 text-red-800"
                      }`}
                    >
                      {user.is_active ? t("tenantAdmin.users.active") : t("tenantAdmin.users.disabled")}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {user.created_at ? new Date(user.created_at).toLocaleDateString() : "-"}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm space-x-3">
                    <button
                      onClick={() => handleAssignRoles(user)}
                      className="text-indigo-600 hover:text-indigo-900"
                    >
                      {t("tenantAdmin.users.assignRoles")}
                    </button>
                    <button
                      onClick={() => handleToggleActive(user)}
                      className={`${
                        user.is_active
                          ? "text-red-600 hover:text-red-900"
                          : "text-green-600 hover:text-green-900"
                      }`}
                    >
                      {user.is_active ? t("tenantAdmin.users.disable") : t("tenantAdmin.users.enable")}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showRoleDialog && selectedUser && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold mb-4">
              {t("tenantAdmin.users.assignRolesTitle", { email: selectedUser.email })}
            </h3>

            <div className="space-y-2 mb-6">
              {roles.map((role) => (
                <label key={role.id} className="flex items-center space-x-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selectedRoles.includes(role.name)}
                    onChange={() => toggleRole(role.name)}
                    className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                  />
                  <span className="text-gray-700">{role.name}</span>
                </label>
              ))}
            </div>

            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowRoleDialog(false)}
                className="px-4 py-2 text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200"
              >
                {t("tenantAdmin.users.cancel")}
              </button>
              <button
                onClick={handleSaveRoles}
                className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
              >
                {t("tenantAdmin.users.save")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
