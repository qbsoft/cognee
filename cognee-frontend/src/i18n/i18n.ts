"use client";

import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import enTranslation from "@/locales/en.json";
import zhTranslation from "@/locales/zh.json";

// 初始化 i18next
i18n
    .use(initReactI18next) // 将 i18next 传递给 react-i18next
    .init({
        resources: {
            en: {
                translation: enTranslation,
            },
            zh: {
                translation: zhTranslation,
            },
        },
        lng: typeof window !== "undefined"
            ? localStorage.getItem("language") || "en"
            : "en", // 默认语言
        fallbackLng: "en", // 回退语言
        interpolation: {
            escapeValue: false, // React 已经安全处理了
        },
        // 同步初始化，避免 SSR hydration 不匹配
        // （否则 Next.js 预渲染时返回 key 字符串，客户端水合后才显示翻译）
        initImmediate: false,
    });

export default i18n;
