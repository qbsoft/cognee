"use client";

import { useTranslation } from "react-i18next";
import "@/i18n/i18n"; // 确保 i18n 已初始化

export default function LanguageSwitcher() {
    const { i18n } = useTranslation();

    const changeLanguage = (lng: string) => {
        i18n.changeLanguage(lng);
        if (typeof window !== "undefined") {
            localStorage.setItem("language", lng);
        }
    };

    const currentLanguage = i18n.language || "en";

    return (
        <div className="flex gap-2 items-center">
            <button
                onClick={() => changeLanguage("en")}
                className={`px-3 py-1 text-xs rounded ${currentLanguage === "en"
                        ? "bg-indigo-600 text-white"
                        : "bg-gray-200 text-gray-700 hover:bg-gray-300"
                    }`}
            >
                EN
            </button>
            <button
                onClick={() => changeLanguage("zh")}
                className={`px-3 py-1 text-xs rounded ${currentLanguage === "zh"
                        ? "bg-indigo-600 text-white"
                        : "bg-gray-200 text-gray-700 hover:bg-gray-300"
                    }`}
            >
                中文
            </button>
        </div>
    );
}
