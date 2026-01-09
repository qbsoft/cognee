"use client";

import { useState, useEffect } from "react";
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
      // 获取所有功能权限列表
      const response = await fetch("/v1/permissions/function-permissions");
      const data = await response.json();
      setPermissions(data.permissions || []);
    } catch (error) {
      console.error("获取权限列表失败:", error);
      toast.error("获取权限列表失败");
    }
  };

  const fetchRoles = async () => {
    try {
      // 获取当前租户的角色列表
      const response = await fetch("/v1/permissions/my-tenant/roles");
      const data = await response.json();
      setRoles(data.roles || []);
    } catch (error) {
      console.error("获取角色列表失败:", error);
      toast.error("获取角色列表失败");
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
      console.error("获取角色权限失败:", error);
      toast.error("获取角色权限失败");
    } finally {
      setLoading(false);
    }
  };

  const handleTogglePermission = async (permissionId: string, hasPermission: boolean) => {
    if (!selectedRole) {
      toast.error("请先选择角色");
      return;
    }

    try {
      if (hasPermission) {
        // 移除权限
        await fetch(`/v1/permissions/roles/${selectedRole}/permissions/${permissionId}`, {
          method: "DELETE",
        });
        toast.success("权限已移除");
      } else {
        // 添加权限
        await fetch(`/v1/permissions/roles/${selectedRole}/permissions/${permissionId}`, {
          method: "POST",
        });
        toast.success("权限已添加");
      }

      // 刷新角色权限
      await fetchRolePermissions(selectedRole);
    } catch (error) {
      console.error("更新权限失败:", error);
      toast.error("更新权限失败");
    }
  };

  // 按类别分组权限
  const groupedPermissions = permissions.reduce((acc, perm) => {
    const category = perm.category || "其他";
    if (!acc[category]) {
      acc[category] = [];
    }
    acc[category].push(perm);
    return acc;
  }, {} as Record<string, Permission[]>);

  return (
    <div className="space-y-6">
      <div className="bg-blue-50 p-4 rounded-lg">
        <h3 className="font-semibold text-blue-900 mb-2">功能权限管理</h3>
        <p className="text-sm text-blue-700">
          为角色分配功能权限，控制用户可以访问的菜单和执行的操作。
        </p>
      </div>

      {/* 角色选择 */}
      <div className="bg-white p-4 rounded-lg border border-gray-200">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          选择角色
        </label>
        <select
          value={selectedRole}
          onChange={(e) => setSelectedRole(e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          <option value="">-- 请选择角色 --</option>
          {roles.map((role) => (
            <option key={role.id} value={role.id}>
              {role.name}
            </option>
          ))}
        </select>
      </div>

      {/* 权限列表 */}
      {selectedRole ? (
        loading ? (
          <div className="text-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mx-auto"></div>
            <p className="mt-2 text-gray-600">加载中...</p>
          </div>
        ) : (
          <div className="space-y-4">
            {Object.keys(groupedPermissions).length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                暂无可用权限
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
                            <div className="text-xs text-gray-400 mt-1">代码: {perm.code}</div>
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
          请先选择一个角色以管理其权限
        </div>
      )}
    </div>
  );
}
