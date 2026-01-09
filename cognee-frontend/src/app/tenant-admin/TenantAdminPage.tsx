"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import TenantInfoPanel from "./TenantInfoPanel";
import TenantUsersPanel from "./TenantUsersPanel";
import TenantRolesPanel from "./TenantRolesPanel";
import TenantPermissionsPanel from "./TenantPermissionsPanel";
import TenantApiKeysPanel from "./TenantApiKeysPanel";

export default function TenantAdminPage() {
  const [activeTab, setActiveTab] = useState<"info" | "users" | "roles" | "permissions" | "api-keys">("info");
  const router = useRouter();

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-indigo-50">
      <div className="container mx-auto px-4 py-8">
        {/* 页面标题 */}
        <div className="mb-8">
          <div className="flex items-center space-x-4 mb-4">
            <button
              onClick={() => router.push('/dashboard')}
              className="flex items-center text-gray-600 hover:text-gray-900 transition-colors"
            >
              <svg className="w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
              返回主页
            </button>
          </div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">权限管理中心</h1>
          <p className="text-gray-600">查看您的租户信息，管理您的用户、角色、权限</p>
        </div>

        {/* 标签切换 */}
        <div className="mb-6 border-b border-gray-200">
          <nav className="-mb-px flex space-x-8">
            <button
              onClick={() => setActiveTab("info")}
              className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === "info"
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
              }`}
            >
              租户信息
            </button>
            <button
              onClick={() => setActiveTab("users")}
              className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === "users"
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
              }`}
            >
              用户管理
            </button>
            <button
              onClick={() => setActiveTab("roles")}
              className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === "roles"
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
              }`}
            >
              角色管理
            </button>
            <button
              onClick={() => setActiveTab("permissions")}
              className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === "permissions"
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
              }`}
            >
              权限管理
            </button>
            <button
              onClick={() => setActiveTab("api-keys")}
              className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === "api-keys"
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
              }`}
            >
              API Keys
            </button>
          </nav>
        </div>

        {/* 内容区域 */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          {activeTab === "info" && <TenantInfoPanel />}
          {activeTab === "users" && <TenantUsersPanel />}
          {activeTab === "roles" && <TenantRolesPanel />}
          {activeTab === "permissions" && <TenantPermissionsPanel />}
          {activeTab === "api-keys" && <TenantApiKeysPanel />}
        </div>
      </div>
    </div>
  );
}
