"use client";

import { useState, useEffect } from "react";
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
      console.error("获取角色列表失败:", error);
      toast.error("获取角色列表失败，请稍后重试");
    } finally {
      setLoading(false);
    }
  };

  const handleCreateRole = async () => {
    if (!newRoleName.trim()) {
      toast.error("请输入角色名称");
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
        toast.success("角色创建成功！");
        setShowCreateDialog(false);
        setNewRoleName("");
        setNewRoleDescription("");
        await fetchRoles();
      } else {
        const data = await response.json();
        toast.error(data.detail || "创建角色失败");
      }
    } catch (error) {
      console.error("创建角色失败:", error);
      toast.error("创建角色失败，请稍后重试");
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
        toast.success("角色更新成功！");
        setShowEditDialog(false);
        setSelectedRole(null);
        setNewRoleName("");
        setNewRoleDescription("");
        await fetchRoles();
      } else {
        toast.error("更新角色失败，请检查权限");
      }
    } catch (error) {
      console.error("更新角色失败:", error);
      toast.error("更新角色失败，请稍后重试");
    }
  };

  const handleDeleteRole = async (roleId: string, roleName: string) => {
    if (!confirm(`确定要删除角色 "${roleName}" 吗？此操作不可恢复。`)) {
      return;
    }

    try {
      const response = await fetch(`/v1/permissions/roles/${roleId}`, {
        method: "DELETE",
      });

      if (response.ok) {
        toast.success("角色删除成功！");
        await fetchRoles();
      } else {
        const data = await response.json();
        toast.error(data.detail || "删除角色失败");
      }
    } catch (error) {
      console.error("删除角色失败:", error);
      toast.error("删除角色失败，请稍后重试");
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
        <p className="mt-4 text-gray-500">加载中...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-semibold text-gray-900">角色管理</h2>
        <button
          onClick={() => setShowCreateDialog(true)}
          className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
        >
          + 创建角色
        </button>
      </div>

      {roles.length === 0 ? (
        <div className="text-center py-8 text-gray-500">暂无角色</div>
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
                创建时间: {new Date(role.created_at).toLocaleDateString("zh-CN")}
              </div>

              {role.user_count !== undefined && (
                <div className="text-sm text-gray-600 mb-3">
                  {role.user_count} 名用户
                </div>
              )}

              <div className="flex gap-2">
                <button
                  onClick={() => openEditDialog(role)}
                  className="flex-1 text-sm text-indigo-600 hover:text-indigo-800"
                >
                  编辑
                </button>
                <button
                  onClick={() => handleDeleteRole(role.id, role.name)}
                  className="flex-1 text-sm text-red-600 hover:text-red-800"
                >
                  删除
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 创建角色对话框 */}
      {showCreateDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold mb-4">创建新角色</h3>

            <div className="space-y-4 mb-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  角色名称 *
                </label>
                <input
                  type="text"
                  value={newRoleName}
                  onChange={(e) => setNewRoleName(e.target.value)}
                  placeholder="例如：项目经理"
                  className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  角色描述
                </label>
                <textarea
                  value={newRoleDescription}
                  onChange={(e) => setNewRoleDescription(e.target.value)}
                  placeholder="简要描述角色职责..."
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
                取消
              </button>
              <button
                onClick={handleCreateRole}
                className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
              >
                创建
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 编辑角色对话框 */}
      {showEditDialog && selectedRole && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold mb-4">编辑角色</h3>

            <div className="space-y-4 mb-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  角色名称 *
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
                  角色描述
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
                取消
              </button>
              <button
                onClick={handleEditRole}
                className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
              >
                保存
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
