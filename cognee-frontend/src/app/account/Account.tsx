"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { BackIcon } from "@/ui/Icons";
import { CTAButton, Input } from "@/ui/elements";
import Header from "@/ui/Layout/Header";
import { useAuthenticatedUser } from "@/modules/auth";
import toast from "react-hot-toast";
import { fetch } from "@/utils";

export default function Account() {
  const router = useRouter();
  const { user } = useAuthenticatedUser();
  const [showChangePassword, setShowChangePassword] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isChangingPassword, setIsChangingPassword] = useState(false);

  const account = {
    name: user ? user.name || user.email : "NN",
    email: user?.email || "",
  };

  // 修改密码
  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();

    if (newPassword !== confirmPassword) {
      toast.error("两次输入的密码不一致");
      return;
    }

    if (newPassword.length < 8) {
      toast.error("密码长度不能少于8位");
      return;
    }

    setIsChangingPassword(true);

    try {
      // 调用修改密码API
      // 注意: FastAPI Users 默认的修改密码需要先忘记密码流程
      // 这里我们直接使用简单的方式：重新登录来验证旧密码
      const loginResponse = await fetch("/v1/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: new URLSearchParams({
          username: account.email,
          password: currentPassword,
        }),
      });

      if (!loginResponse.ok) {
        toast.error("当前密码错误");
        setIsChangingPassword(false);
        return;
      }

      // TODO: 调用修改密码API（需要后端支持）
      // 暂时显示提示
      toast.error("修改密码功能正在开发中，请使用忘记密码功能");
      setIsChangingPassword(false);
      
      // 清空表单
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setShowChangePassword(false);
    } catch (error) {
      toast.error("修改密码失败，请稍后重试");
      setIsChangingPassword(false);
    }
  };

  // 登出
  const handleLogout = async () => {
    try {
      // 调用登出API
      await fetch("/v1/auth/logout", {
        method: "POST",
      });

      // 清除本地存储（如果有）
      if (typeof window !== "undefined") {
        localStorage.clear();
        sessionStorage.clear();
      }

      // 跳转到登录页
      toast.success("已成功登出");
      router.push("/auth/login");
    } catch (error) {
      console.error("登出失败:", error);
      toast.error("登出失败，请稍后重试");
    }
  };

  return (
    <div className="h-full max-w-[1920px] mx-auto">
      <Header user={user} />

      <div className="relative flex flex-row items-start gap-2.5">
        <Link href="/dashboard" className="flex-1/5 py-4 px-5 flex flex-row items-center gap-5">
          <BackIcon />
          <span>back</span>
        </Link>
        <div className="flex-1/5 flex flex-col gap-2.5">
          {/* 账户信息 */}
          <div className="py-4 px-5 rounded-xl bg-white">
            <div className="text-lg font-semibold">账户</div>
            <div className="text-sm text-gray-400 mb-8">管理您的账户设置。</div>
            <div className="space-y-2">
              <div>
                <span className="text-gray-600">用户名：</span>
                <span className="ml-2 font-medium">{account.name}</span>
              </div>
              <div>
                <span className="text-gray-600">邮箱：</span>
                <span className="ml-2 font-medium">{account.email}</span>
              </div>
            </div>
          </div>

          {/* 修改密码 */}
          <div className="py-4 px-5 rounded-xl bg-white">
            <div className="text-lg font-semibold">密码</div>
            <div className="text-sm text-gray-400 mb-4">修改您的登录密码。</div>
            
            {!showChangePassword ? (
              <CTAButton 
                className="w-full" 
                onClick={() => setShowChangePassword(true)}
              >
                修改密码
              </CTAButton>
            ) : (
              <form onSubmit={handleChangePassword} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    当前密码
                  </label>
                  <Input
                    type="password"
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    placeholder="请输入当前密码"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    新密码
                  </label>
                  <Input
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="请输入新密码（至少8位）"
                    required
                    minLength={8}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    确认新密码
                  </label>
                  <Input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="请再次输入新密码"
                    required
                  />
                </div>
                <div className="flex gap-2">
                  <button
                    type="submit"
                    disabled={isChangingPassword}
                    className="flex-1 bg-indigo-600 text-white rounded-lg px-4 py-2 hover:bg-indigo-700 disabled:opacity-50"
                  >
                    {isChangingPassword ? "修改中..." : "确认修改"}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowChangePassword(false);
                      setCurrentPassword("");
                      setNewPassword("");
                      setConfirmPassword("");
                    }}
                    className="flex-1 bg-gray-200 text-gray-700 rounded-lg px-4 py-2 hover:bg-gray-300"
                  >
                    取消
                  </button>
                </div>
              </form>
            )}
          </div>

          {/* 登出 */}
          <div className="py-4 px-5 rounded-xl bg-white">
            <div className="text-lg font-semibold mb-2">登出</div>
            <div className="text-sm text-gray-400 mb-4">退出当前账户。</div>
            <button
              onClick={handleLogout}
              className="w-full bg-red-600 text-white rounded-lg px-4 py-2 hover:bg-red-700"
            >
              登出
            </button>
          </div>

          {/* Plan */}
          <div className="py-4 px-5 rounded-xl bg-white">
            <div className="text-lg font-semibold">Plan</div>
            <div className="text-sm text-gray-400 mb-8">You are using open-source version. Subscribe to get access to hosted cognee with your data!</div>
            <Link href="/plan">
              <CTAButton className="w-full"><span className="">Select a plan</span></CTAButton>
            </Link>
          </div>
        </div>
        <div className="flex-1/5 py-4 px-5 rounded-xl">
        </div>
        <div className="flex-1/5 py-4 px-5 rounded-xl">
        </div>
        <div className="flex-1/5 py-4 px-5 rounded-xl">
        </div>
      </div>
    </div>
  );
}
