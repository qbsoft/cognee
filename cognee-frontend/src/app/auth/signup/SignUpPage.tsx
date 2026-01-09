"use client";

import Link from "next/link";
import Image from "next/image";
import { Suspense } from "react";

import EnhancedSignUpForm from "./EnhancedSignUpForm";

export default function SignUpPage() {
  return (
    <div className="m-auto w-full max-w-md shadow-xl rounded-xl">
      <div className="flex flex-col px-10 py-16 bg-white border-1 rounded-xl border-indigo-600 overflow-hidden">
        <Image src="/images/cognee-logo-with-text.png" alt="Cognee logo" width={176} height={46} className="h-12 w-44 self-center mb-16" />

        <h1 className="self-center text-xl mb-4">欢迎注册</h1>
        <p className="self-center mb-10 text-gray-600">开始使用 Cognee</p>

        <Suspense fallback={<div className="text-center">加载中...</div>}>
          <EnhancedSignUpForm />
        </Suspense>

        <p className="text-center mt-2 text-sm">
          <Link href="/auth/login" className="text-indigo-600 hover:text-indigo-800">
            {"已有账号？去登录 ->"}
          </Link>
        </p>
      </div>
    </div>
  );
}
