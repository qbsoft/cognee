"use client";

import { useState, useEffect } from "react";
import { fetch } from "@/utils";

interface User {
  id: string;
  email: string;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  roles?: string[];
}

interface TenantUsersModalProps {
  tenantId: string;
  tenantName: string;
  onClose: () => void;
}

export default function TenantUsersModal({ tenantId, tenantName, onClose }: TenantUsersModalProps) {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchUsers();
  }, [tenantId]);

  const fetchUsers = async () => {
    setLoading(true);
    try {
      // 调用后端API获取租户用户列表
      const response = await fetch(`/v1/permissions/tenants/${tenantId}/users`);
      const data = await response.json();
      setUsers(data.users || []);
    } catch (error) {
      console.error("获取租户用户失败:", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div 
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div 
        className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[80vh] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
          <div>
            <h2 className="text-xl font-semibold text-gray-900">租户用户列表</h2>
            <p className="text-sm text-gray-600 mt-1">租户: {tenantName}</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
          >
            ×
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-4 overflow-y-auto max-h-[calc(80vh-140px)]">
          {loading ? (
            <div className="text-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mx-auto"></div>
              <p className="mt-2 text-gray-600">加载中...</p>
            </div>
          ) : users.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              该租户暂无用户
            </div>
          ) : (
            <div className="space-y-3">
              {users.map((user) => (
                <div
                  key={user.id}
                  className="p-4 border border-gray-200 rounded-lg hover:border-indigo-300 transition-colors"
                >
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <div className="font-medium text-gray-900">{user.email}</div>
                      <div className="text-sm text-gray-500 mt-1">ID: {user.id}</div>
                      <div className="text-sm text-gray-400 mt-1">
                        创建时间: {new Date(user.created_at).toLocaleString("zh-CN")}
                      </div>
                      
                      {/* 角色标签 */}
                      {user.roles && user.roles.length > 0 && (
                        <div className="flex gap-2 mt-2">
                          {user.roles.map((role, idx) => (
                            <span
                              key={idx}
                              className="px-2 py-1 bg-indigo-100 text-indigo-700 text-xs rounded-full"
                            >
                              {role}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                    
                    <div className="flex gap-2">
                      <span className={`px-2 py-1 text-xs rounded-full ${
                        user.is_active 
                          ? "bg-green-100 text-green-700" 
                          : "bg-red-100 text-red-700"
                      }`}>
                        {user.is_active ? "已激活" : "未激活"}
                      </span>
                      <span className={`px-2 py-1 text-xs rounded-full ${
                        user.is_verified 
                          ? "bg-blue-100 text-blue-700" 
                          : "bg-gray-100 text-gray-700"
                      }`}>
                        {user.is_verified ? "已验证" : "未验证"}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 flex justify-between items-center">
          <div className="text-sm text-gray-600">
            共 {users.length} 个用户
          </div>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
          >
            关闭
          </button>
        </div>
      </div>
    </div>
  );
}
