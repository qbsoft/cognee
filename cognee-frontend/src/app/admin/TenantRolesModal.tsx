"use client";

import { useState, useEffect } from "react";
import { fetch } from "@/utils";

interface Role {
  id: string;
  name: string;
  created_at: string;
  user_count?: number;
}

interface TenantRolesModalProps {
  tenantId: string;
  tenantName: string;
  onClose: () => void;
}

export default function TenantRolesModal({ tenantId, tenantName, onClose }: TenantRolesModalProps) {
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchRoles();
  }, [tenantId]);

  const fetchRoles = async () => {
    setLoading(true);
    try {
      // 调用后端API获取租户角色列表
      const response = await fetch(`/v1/permissions/tenants/${tenantId}/roles`);
      const data = await response.json();
      setRoles(data.roles || []);
    } catch (error) {
      console.error("获取租户角色失败:", error);
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
        className="bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[80vh] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
          <div>
            <h2 className="text-xl font-semibold text-gray-900">租户角色列表</h2>
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
          ) : roles.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              该租户暂无角色
            </div>
          ) : (
            <div className="space-y-3">
              {roles.map((role) => (
                <div
                  key={role.id}
                  className="p-4 border border-gray-200 rounded-lg hover:border-indigo-300 transition-colors"
                >
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <div className="font-medium text-gray-900 text-lg">{role.name}</div>
                      <div className="text-sm text-gray-500 mt-1">ID: {role.id}</div>
                      <div className="text-sm text-gray-400 mt-1">
                        创建时间: {new Date(role.created_at).toLocaleString("zh-CN")}
                      </div>
                    </div>
                    
                    {role.user_count !== undefined && (
                      <div className="text-sm text-gray-600">
                        <span className="font-medium">{role.user_count}</span> 个用户
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 flex justify-between items-center">
          <div className="text-sm text-gray-600">
            共 {roles.length} 个角色
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
