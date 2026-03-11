"use client";

import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { fetch, useBoolean } from "@/utils";
import { CTAButton, Input } from "@/ui/elements";
import { LoadingIndicator } from "@/ui/App";
import { useSearchParams } from "next/navigation";

const ERROR_KEYS: Record<string, string> = {
  REGISTER_USER_ALREADY_EXISTS: "auth.signup.errors.userExists",
  REGISTER_INVALID_PASSWORD: "auth.signup.errors.invalidPassword",
  INVALID_TENANT_CODE: "auth.signup.errors.invalidTenantCode",
  INVALID_INVITE_TOKEN: "auth.signup.errors.invalidInviteToken",
  TENANT_NOT_FOUND: "auth.signup.errors.tenantNotFound",
};

export default function EnhancedSignUpForm() {
  const { t } = useTranslation();
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
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const payload: any = {
        email,
        password,
      };

      if (registrationMode === "invite" && inviteToken) {
        payload.invite_token = inviteToken;
      } else if (registrationMode === "code") {
        if (!tenantCode.trim()) {
          setRegisterError(t("auth.signup.missingTenantCode"));
          enableRegister();
          return;
        }
        payload.tenant_code = tenantCode.trim().toUpperCase();
      }

      await fetch("/v1/auth/register", {
        method: "POST",
        body: JSON.stringify(payload),
        headers: {
          "Content-Type": "application/json",
        },
      });

      window.location.href = "/auth/login?registered=true";
    } catch (error: any) {
      const errorKey = ERROR_KEYS[error.detail as string];
      const errorMessage = errorKey
        ? t(errorKey)
        : error.message || t("auth.signup.registerFailed");
      setRegisterError(errorMessage);
    } finally {
      enableRegister();
    }
  };

  return (
    <form onSubmit={handleRegister} className="flex flex-col gap-4">
      {inviteToken && (
        <div className="p-3 bg-indigo-50 border border-indigo-200 rounded-lg text-sm text-indigo-700">
          {t("auth.signup.inviteBanner")}
        </div>
      )}

      {!inviteToken && (
        <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-700">
          {t("auth.signup.tenantCodeBanner")}
        </div>
      )}

      {!inviteToken && (
        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium text-gray-700">
            {t("auth.signup.tenantCodeLabel")}
          </span>
          <Input
            type="text"
            value={tenantCode}
            onChange={(e) => setTenantCode(e.target.value.toUpperCase())}
            required
            placeholder={t("auth.signup.tenantCodePlaceholder")}
            maxLength={6}
            pattern="[A-Z0-9]{6}"
            className="font-mono tracking-wider"
          />
          <span className="text-xs text-gray-500">
            {t("auth.signup.tenantCodeHint")}
          </span>
        </label>
      )}

      <label className="flex flex-col gap-1">
        <span className="text-sm font-medium text-gray-700">{t("auth.signup.emailLabel")}</span>
        <Input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          placeholder="your@email.com"
        />
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-sm font-medium text-gray-700">{t("auth.signup.passwordLabel")}</span>
        <Input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          placeholder={t("auth.signup.passwordPlaceholder")}
          minLength={8}
        />
        <span className="text-xs text-gray-500">
          {t("auth.signup.passwordHint")}
        </span>
      </label>

      <CTAButton className="mt-6 mb-2" type="submit" disabled={isRegistering}>
        {isRegistering ? (
          <>
            {t("auth.signup.registering")}
            <LoadingIndicator />
          </>
        ) : (
          t("auth.signup.registerButton")
        )}
      </CTAButton>

      {registerError && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          ⚠️ {registerError}
        </div>
      )}

      {inviteToken && (
        <div className="text-xs text-gray-500 text-center">
          {t("auth.signup.inviteAutoJoin")}
        </div>
      )}
    </form>
  );
}
