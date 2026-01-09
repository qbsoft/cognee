"use client";

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { fetch, useBoolean } from "@/utils";
import { CTAButton, Input } from "@/ui/elements";
import { LoadingIndicator } from '@/ui/App';

interface AuthFormPayload extends HTMLFormElement {
  email: HTMLInputElement;
  password: HTMLInputElement;
}

const errorsMap = {
  LOGIN_BAD_CREDENTIALS: "Invalid username or password",
  REGISTER_USER_ALREADY_EXISTS: "User already exists",
};

const defaultFormatPayload: (data: { email: string; password: string; }) => object = (data) => data;

interface AuthFormProps {
  submitButtonText?: string;
  authUrl?: string;
  formatPayload?: (data: { email: string; password: string; }) => object;
  onSignInSuccess?: () => void;
  emailPlaceholder?: string;
  passwordPlaceholder?: string;
}

export default function AuthForm({
  submitButtonText,
  authUrl = "/v1/auth/login",
  formatPayload = defaultFormatPayload,
  onSignInSuccess = () => window.location.href = "/",
  emailPlaceholder,
  passwordPlaceholder,
}: AuthFormProps) {
  const { t } = useTranslation();
  const {
      value: isSigningIn,
      setTrue: disableSignIn,
      setFalse: enableSignIn,
    } = useBoolean(false);

    const [signInError, setSignInError] = useState<string | null>(null);

    const signIn = (event: React.FormEvent<AuthFormPayload>) => {
      event.preventDefault();
      const formElements = event.currentTarget;

      // Backend expects username and password fields
      const authCredentials = {
        email: formElements.email.value,
        password: formElements.password.value,
      };

      setSignInError(null);
      disableSignIn();

      const formattedPayload = formatPayload(authCredentials);

      console.log("Attempting login to:", authUrl);
      console.log("Login payload:", formattedPayload instanceof URLSearchParams ? formattedPayload.toString() : JSON.stringify(formattedPayload));

      // 使用 fetch 工具函数（从 @/utils 导入），它会自动处理 URL、credentials 和错误
      // fetch 工具函数会自动添加 /api 前缀并设置 credentials: "include"
      fetch(authUrl, {
        method: "POST",
        body: formattedPayload instanceof URLSearchParams ? formattedPayload.toString() : JSON.stringify(formattedPayload),
        headers: {
          "Content-Type": formattedPayload instanceof URLSearchParams ? "application/x-www-form-urlencoded" : "application/json",
        },
      })
        .then((response) => {
          console.log("Login response status:", response.status);
          console.log("Login response ok:", response.ok);
          
          // fetch 工具函数已经处理了错误，如果到这里说明响应是成功的
          // 但我们需要确保状态码是 200 或 204
          if (response.status >= 200 && response.status < 300) {
            console.log("Login successful, calling onSignInSuccess");
            onSignInSuccess();
          } else {
            // 如果状态码不在成功范围内，尝试解析错误
            return response.json().then((errorData) => {
              console.error("Login error response:", errorData);
              throw { detail: errorData.detail || "LOGIN_FAILED", message: errorData.detail || "Login failed" };
            }).catch((jsonError) => {
              // 如果无法解析 JSON，使用状态码作为错误
              throw { detail: "LOGIN_FAILED", message: `Login failed with status ${response.status}` };
            });
          }
        })
        .catch(error => {
          console.error("Login error:", error);
          console.error("Error type:", typeof error);
          console.error("Error keys:", Object.keys(error || {}));
          console.error("Error message:", error?.message);
          console.error("Error detail:", error?.detail);
          
          // 处理不同类型的错误
          let errorMsg = "Login failed. Please check your credentials.";
          
          if (error?.detail) {
            if (error.detail === "LOGIN_BAD_CREDENTIALS") {
              errorMsg = t('auth.login.invalidCredentials');
            } else if (errorsMap[error.detail as keyof typeof errorsMap]) {
              errorMsg = errorsMap[error.detail as keyof typeof errorsMap];
            } else {
              errorMsg = error.detail;
            }
          } else if (error?.message) {
            errorMsg = error.message;
          }
          
          setSignInError(errorMsg);
        })
        .finally(() => {
          console.log("Login attempt finished");
          enableSignIn();
        });
    };

    return (
      <form onSubmit={signIn} className="flex flex-col gap-4">
        <label className="flex flex-col gap-1">
          {t('auth.login.emailLabel')}*
          <Input 
            type="email" 
            name="email" 
            required 
            placeholder={emailPlaceholder || t('auth.login.emailPlaceholder')} 
          />
        </label>
        <label className="flex flex-col gap-1">
          {t('auth.login.passwordLabel')}*
          <Input 
            type="password" 
            name="password" 
            required 
            placeholder={passwordPlaceholder || t('auth.login.passwordPlaceholder')} 
          />
        </label>
        <CTAButton className="mt-6 mb-2" type="submit">
          {submitButtonText || t('auth.login.loginButton')}
          {isSigningIn && <LoadingIndicator />}
        </CTAButton>
        {signInError && (
          <span className="text-s text-red-500 mb-4">{signInError}</span>
        )}
      </form>
    );
}
