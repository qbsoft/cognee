"use client";

import { useEffect } from "react";
import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useTranslation } from "react-i18next";
import i18n from "@/i18n/i18n";
import apiFetch from "@/utils/fetch";

import AuthForm from "../AuthForm";

export default function LoginPage() {
  const router = useRouter();
  const { t, i18n: i18nInstance } = useTranslation();

  // 初始化 i18n
  useEffect(() => {
    // 确保 i18n已加载
    if (!i18nInstance.isInitialized) {
      i18nInstance.init();
    }
  }, [i18nInstance]);

  // 语言切换函数
  const toggleLanguage = () => {
    const newLang = i18nInstance.language === 'en' ? 'zh' : 'en';
    i18nInstance.changeLanguage(newLang);
    if (typeof window !== 'undefined') {
      localStorage.setItem('language', newLang);
    }
  };

  const handleLoginSuccess = async () => {
    // 登录成功后,等待一段时间确保浏览器已经设置了 cookie
    // 这很重要,因为登录请求返回的 Set-Cookie 响应头需要时间被浏览器处理
    await new Promise(resolve => setTimeout(resolve, 500));
    
    // 检查 Cookie 是否已设置
    console.log("Checking cookies after login...");
    const cookies = document.cookie;
    console.log("Current cookies:", cookies);
    
    // 获取用户信息,根据角色跳转到不同页面
    try {
      console.log("Fetching user info from /v1/auth/me...");
      const response = await apiFetch("/v1/auth/me");
      
      if (!response.ok) {
        console.error("Failed to get user info, status:", response.status);
        const errorText = await response.text();
        console.error("Error response:", errorText);
        throw new Error(`Failed to get user info: ${response.status}`);
      }
      
      const user = await response.json();
      console.log("User info retrieved:", user);
      
      // 存储token到localStorage供WebSocket使用
      // 注意: 这里我们不能从 cookie 读取 token(因为是httpOnly)
      // 所以我们需要从响应头或响应体获取
      // 但是登录接口没有返回token,我们需要从response headers中提取
      const setCookieHeader = response.headers.get('set-cookie');
      console.log("Set-Cookie header:", setCookieHeader);
      
      // 由于浏览器安全限制,无法读取set-cookie响应头
      // 我们需要让后端在登录响应中返回token
      // 暂时使用一个占位值,等待后端修改
      if (user.access_token) {
        localStorage.setItem('auth_token', user.access_token);
        console.log("Token stored to localStorage");
      } else {
        console.warn("No access_token in user response, WebSocket may not work");
      }
      
      // 超级管理员 -> /admin
      if (user.is_superuser) {
        router.push("/admin");
      }
      // 租户管理员(拥有"管理员"角色) -> /tenant-admin
      else if (user.roles && user.roles.includes("管理员")) {
        router.push("/tenant-admin");
      }
      // 普通用户 -> /dashboard
      else {
        router.push("/dashboard");
      }
    } catch (error) {
      console.error("获取用户信息失败:", error);
      console.error("Error details:", {
        message: error?.message,
        status: error?.status,
        detail: error?.detail,
      });
      
      // 如果获取用户信息失败,默认跳转到 dashboard
      // dashboard 页面会再次尝试获取用户信息
      router.push("/dashboard");
    }
  };

  return (
    <div className="m-auto w-full max-w-md shadow-xl rounded-xl">
      <div className="flex flex-col px-10 py-16 bg-white border-1 rounded-xl border-indigo-600 overflow-hidden">
        {/* 语言切换按钮 */}
        <div className="flex justify-end mb-4">
          <button
            onClick={toggleLanguage}
            className="px-3 py-1 text-sm text-indigo-600 hover:text-indigo-800 border border-indigo-300 rounded-md hover:bg-indigo-50 transition-colors"
          >
            {i18nInstance.language === 'en' ? '中文' : 'English'}
          </button>
        </div>

        <Image src="/images/cognee-logo-with-text.png" alt="Cognee logo" width={176} height={46} className="h-12 w-44 self-center mb-16" />

        <h1 className="self-center text-xl mb-4">{t('auth.login.title')}</h1>
        <p className="self-center mb-10 text-gray-600">{t('auth.login.subtitle')}</p>

        <AuthForm
          authUrl="/v1/auth/login"
          formatPayload={formatPayload}
          onSignInSuccess={handleLoginSuccess}
        />

        <p className="text-center mt-2 text-sm">
          <Link href="/auth/signup" className="text-indigo-600 hover:text-indigo-800">
            {t('auth.login.signupLink')}
          </Link>
        </p>
      </div>
    </div>
  );
}

function formatPayload(data: { email: string, password: string }) {
  const payload = new URLSearchParams();

  payload.append("username", data.email);
  payload.append("password", data.password);

  return payload;
}
