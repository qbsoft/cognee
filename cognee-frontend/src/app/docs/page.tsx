"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function DocsPage() {
  const router = useRouter();

  useEffect(() => {
    // 重定向到后端API文档
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL || "http://localhost:8000";
    window.location.href = `${backendUrl}/docs`;
  }, []);

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-100">
      <div className="text-center">
        <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-indigo-600 mx-auto mb-4"></div>
        <p className="text-gray-600 text-lg">正在跳转到API文档...</p>
        <p className="text-gray-500 text-sm mt-2">Redirecting to API Documentation...</p>
      </div>
    </div>
  );
}
