"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthenticatedUser } from "@/modules/auth";

export default function HomePage() {
  const router = useRouter();
  const { user, isLoading } = useAuthenticatedUser();

  useEffect(() => {
    if (!isLoading) {
      if (user) {
        // 已登录，跳转到 dashboard
        router.push("/dashboard");
      } else {
        // 未登录，跳转到登录页
        router.push("/auth/login");
      }
    }
  }, [user, isLoading, router]);

  // 显示加载状态
  return (
    <div className="flex items-center justify-center h-screen">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto"></div>
        <p className="mt-4 text-gray-600">Loading...</p>
      </div>
    </div>
  );
}
