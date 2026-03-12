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
import { useTranslation } from "react-i18next";

export default function Account() {
  const router = useRouter();
  const { user } = useAuthenticatedUser();
  const { t } = useTranslation();
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
      toast.error(t("account.errors.passwordMismatch"));
      return;
    }

    if (newPassword.length < 8) {
      toast.error(t("account.errors.passwordTooShort"));
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
        toast.error(t("account.errors.wrongPassword"));
        setIsChangingPassword(false);
        return;
      }

      // TODO: 调用修改密码API（需要后端支持）
      // 暂时显示提示
      toast.error(t("account.errors.changePasswordPending"));
      setIsChangingPassword(false);

      // 清空表单
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setShowChangePassword(false);
    } catch (error) {
      toast.error(t("account.errors.changeFailed"));
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
      toast.success(t("account.logoutSuccess"));
      router.push("/auth/login");
    } catch (error) {
      console.error("登出失败:", error);
      toast.error(t("account.errors.logoutFailed"));
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
            <div className="text-lg font-semibold">{t("account.title")}</div>
            <div className="text-sm text-gray-400 mb-8">{t("account.subtitle")}</div>
            <div className="space-y-2">
              <div>
                <span className="text-gray-600">{t("account.username")}</span>
                <span className="ml-2 font-medium">{account.name}</span>
              </div>
              <div>
                <span className="text-gray-600">{t("account.email")}</span>
                <span className="ml-2 font-medium">{account.email}</span>
              </div>
            </div>
          </div>

          {/* 修改密码 */}
          <div className="py-4 px-5 rounded-xl bg-white">
            <div className="text-lg font-semibold">{t("account.passwordSection")}</div>
            <div className="text-sm text-gray-400 mb-4">{t("account.passwordSubtitle")}</div>

            {!showChangePassword ? (
              <CTAButton
                className="w-full"
                onClick={() => setShowChangePassword(true)}
              >
                {t("account.changePassword")}
              </CTAButton>
            ) : (
              <form onSubmit={handleChangePassword} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t("account.currentPassword")}
                  </label>
                  <Input
                    type="password"
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    placeholder={t("account.currentPasswordPlaceholder")}
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t("account.newPassword")}
                  </label>
                  <Input
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder={t("account.newPasswordPlaceholder")}
                    required
                    minLength={8}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t("account.confirmPassword")}
                  </label>
                  <Input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder={t("account.confirmPasswordPlaceholder")}
                    required
                  />
                </div>
                <div className="flex gap-2">
                  <button
                    type="submit"
                    disabled={isChangingPassword}
                    className="flex-1 bg-indigo-600 text-white rounded-lg px-4 py-2 hover:bg-indigo-700 disabled:opacity-50"
                  >
                    {isChangingPassword ? t("account.submitting") : t("account.confirmChange")}
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
                    {t("common.cancel")}
                  </button>
                </div>
              </form>
            )}
          </div>

          {/* 登出 */}
          <div className="py-4 px-5 rounded-xl bg-white">
            <div className="text-lg font-semibold mb-2">{t("account.logoutSection")}</div>
            <div className="text-sm text-gray-400 mb-4">{t("account.logoutSubtitle")}</div>
            <button
              onClick={handleLogout}
              className="w-full bg-red-600 text-white rounded-lg px-4 py-2 hover:bg-red-700"
            >
              {t("account.logoutButton")}
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
