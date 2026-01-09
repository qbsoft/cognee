"use client";

import { useState, useEffect } from "react";
import { CTAButton, Input } from "@/ui/elements";
import { fetch } from "@/utils";

interface Role {
  id: string;
  name: string;
  tenant_id: string;
  created_at: string;
}

export default function RolesPanel() {
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
      alert("创建角色失败，请重试");
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-gray-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-4">创建新角色</h3>
        <div className="flex flex-row gap-3">
          <Input
            type="text"
            placeholder="输入角色名称（例如：Admin, Editor, Viewer）"
            value={newRoleName}
            onChange={(e) => setNewRoleName(e.target.value)}
            className="flex-1"
          />
          <CTAButton onClick={handleCreateRole} disabled={isCreating || !newRoleName.trim()}>
            {isCreating ? "创建中..." : "创建角色"}
          </CTAButton>
        </div>
        <p className="text-sm text-gray-600 mt-2">
          角色用于批量管理权限，可以将用户添加到角色以继承权限
        </p>
      </div>

      <div>
        <h3 className="text-lg font-semibold mb-4">现有角色</h3>
        {roles.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            暂无角色，请创建第一个角色
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
                      ID: {role.id} | 租户: {role.tenant_id}
                    </div>
                  </div>
                  <div className="text-sm text-gray-400">
                    创建时间: {new Date(role.created_at).toLocaleString("zh-CN")}
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
