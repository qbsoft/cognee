"use client";

import { useState, useEffect } from "react";
import { fetch, useBoolean } from "@/utils";
import { CTAButton, Input } from "@/ui/elements";
import { LoadingIndicator } from "@/ui/App";
import { useSearchParams } from "next/navigation";

const errorsMap = {
  REGISTER_USER_ALREADY_EXISTS: "用户已存在",
  REGISTER_INVALID_PASSWORD: "密码不符合要求",
  INVALID_TENANT_CODE: "无效的租户编码",
  INVALID_INVITE_TOKEN: "邀请链接已过期或无效",
  TENANT_NOT_FOUND: "租户不存在",
};

export default function EnhancedSignUpForm() {
  const searchParams = useSearchParams();
  const inviteToken = searchParams?.get("invite_token");

  const {
    value: isRegistering,
    setTrue: disableRegister,
    setFalse: enableRegister,
  } = useBoolean(false);

  const [registerError, setRegisterError] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [tenantCode, setTenantCode] = useState("");
  const [registrationMode, setRegistrationMode] = useState<"invite" | "code">(
    inviteToken ? "invite" : "code"
  );

  useEffect(() => {
    if (inviteToken) {
      setRegistrationMode("invite");
    }
  }, [inviteToken]);

  const handleRegister = async (event: React.FormEvent) => {
    event.preventDefault();

    setRegisterError(null);
    disableRegister();

    try {
      const payload: any = {
        email,
        password,
      };

      // 根据注册模式添加相应字段
      if (registrationMode === "invite" && inviteToken) {
        payload.invite_token = inviteToken;
      } else if (registrationMode === "code") {
        if (!tenantCode.trim()) {
          setRegisterError("请输入租户编码");
          enableRegister();
          return;
        }
        payload.tenant_code = tenantCode.trim().toUpperCase();
      }

      const response = await fetch("/v1/auth/register", {
        method: "POST",
        body: JSON.stringify(payload),
        headers: {
          "Content-Type": "application/json",
        },
      });

      // 注册成功，跳转到登录页
      window.location.href = "/auth/login?registered=true";
    } catch (error: any) {
      const errorMessage =
        errorsMap[error.detail as keyof typeof errorsMap] ||
        error.message ||
        "注册失败，请重试";
      setRegisterError(errorMessage);
    } finally {
      enableRegister();
    }
  };

  return (
    <form onSubmit={handleRegister} className="flex flex-col gap-4">
      {/* 邀请信息提示 */}
      {inviteToken && (
        <div className="p-3 bg-indigo-50 border border-indigo-200 rounded-lg text-sm text-indigo-700">
          ✓ 您正在通过邀请链接注册
        </div>
      )}

      {/* 注册方式选择（只在无邀请令牌时显示） */}
      {!inviteToken && (
        <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-700">
          ℹ️ 请输入您组织提供的租户编码进行注册
        </div>
      )}

      {/* 租户编码输入（无邀请令牌时必须输入） */}
      {!inviteToken && (
        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium text-gray-700">
            租户编码* <span className="text-xs text-gray-500">(6位字符)</span>
          </span>
          <Input
            type="text"
            value={tenantCode}
            onChange={(e) => setTenantCode(e.target.value.toUpperCase())}
            required
            placeholder="输入6位租户编码"
            maxLength={6}
            pattern="[A-Z0-9]{6}"
            className="font-mono tracking-wider"
          />
          <span className="text-xs text-gray-500">
            请输入您组织提供的6位租户编码
          </span>
        </label>
      )}

      {/* 邮箱输入 */}
      <label className="flex flex-col gap-1">
        <span className="text-sm font-medium text-gray-700">邮箱地址*</span>
        <Input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          placeholder="your@email.com"
        />
      </label>

      {/* 密码输入 */}
      <label className="flex flex-col gap-1">
        <span className="text-sm font-medium text-gray-700">密码*</span>
        <Input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          placeholder="至少8位字符"
          minLength={8}
        />
        <span className="text-xs text-gray-500">
          密码至少8位，建议包含字母、数字和特殊字符
        </span>
      </label>

      {/* 注册按钮 */}
      <CTAButton className="mt-6 mb-2" type="submit" disabled={isRegistering}>
        {isRegistering ? (
          <>
            注册中...
            <LoadingIndicator />
          </>
        ) : (
          "注册"
        )}
      </CTAButton>

      {/* 错误提示 */}
      {registerError && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          ⚠️ {registerError}
        </div>
      )}

      {/* 提示信息 */}
      {inviteToken && (
        <div className="text-xs text-gray-500 text-center">
          通过邀请链接注册后，您将自动加入对应的租户
        </div>
      )}
    </form>
  );
}
