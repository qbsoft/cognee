"use client";

import { useState, useEffect } from "react";
import { CTAButton, Input } from "@/ui/elements";
import { fetch } from "@/utils";

interface User {
  id: string;
  email: string;
  is_active: boolean;
  is_verified: boolean;
  tenant_id: string | null;
}

export default function UsersPanel() {
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
      console.error("创建用户失败:", error);
      alert("创建用户失败，请检查邮箱是否已存在");
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-gray-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-4">创建新用户</h3>
        <div className="space-y-3">
          <Input
            type="email"
            placeholder="邮箱地址"
            value={newUserEmail}
            onChange={(e) => setNewUserEmail(e.target.value)}
          />
          <Input
            type="password"
            placeholder="密码"
            value={newUserPassword}
            onChange={(e) => setNewUserPassword(e.target.value)}
          />
          <CTAButton
            onClick={handleCreateUser}
            disabled={isCreating || !newUserEmail.trim() || !newUserPassword.trim()}
            className="w-full"
          >
            {isCreating ? "创建中..." : "创建用户"}
          </CTAButton>
        </div>
        <p className="text-sm text-gray-600 mt-2">
          新用户创建后需要手动分配到租户和角色
        </p>
      </div>

      <div>
        <h3 className="text-lg font-semibold mb-4">现有用户</h3>
        {users.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            正在加载用户列表...
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
                      {user.tenant_id && ` | 租户ID: ${user.tenant_id}`}
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
                      {user.is_active ? "激活" : "未激活"}
                    </span>
                    <span
                      className={`px-2 py-1 rounded text-xs ${
                        user.is_verified
                          ? "bg-blue-100 text-blue-800"
                          : "bg-gray-100 text-gray-800"
                      }`}
                    >
                      {user.is_verified ? "已验证" : "未验证"}
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
