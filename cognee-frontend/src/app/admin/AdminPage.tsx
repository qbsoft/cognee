"use client";

import Link from "next/link";
import { BackIcon } from "@/ui/Icons";
import Header from "@/ui/Layout/Header";
import { useAuthenticatedUser } from "@/modules/auth";
import TenantsPanel from "./TenantsPanel";
import { useTranslation } from "react-i18next";

export default function AdminPage() {
  const { user } = useAuthenticatedUser();
  const { t } = useTranslation();

  return (
    <div className="h-full flex flex-col max-w-[1920px] mx-auto">
      <Header user={user} />

      <div className="flex-1 flex flex-col px-5 pb-5 overflow-hidden">
        <div className="flex flex-row items-center gap-5 py-4">
          <Link href="/dashboard" className="flex flex-row items-center gap-3">
            <BackIcon />
            <span>{t("admin.backToDashboard")}</span>
          </Link>
        </div>

        <div className="bg-white rounded-xl flex-1 flex flex-col overflow-hidden">
          <div className="p-5 border-b border-gray-200">
            <h1 className="text-2xl font-semibold mb-2">{t("admin.title")}</h1>
            <p className="text-gray-600">{t("admin.description")}</p>
          </div>

          {/* 租户管理面板 */}
          <div className="flex-1 overflow-y-auto p-5">
            <TenantsPanel />
          </div>
        </div>
      </div>
    </div>
  );
}
