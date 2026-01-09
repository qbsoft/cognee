"use client";

import Link from "next/link";
import Image from "next/image";
import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useBoolean, fetch } from "@/utils";

import { CloseIcon, CloudIcon, CogneeIcon } from "../Icons";
import { CTAButton, GhostButton, IconButton, Modal, StatusDot } from "../elements";
import LanguageSwitcher from "../elements/LanguageSwitcher";
import syncData from "@/modules/cloud/syncData";
import "@/i18n/i18n";

interface HeaderProps {
  user?: {
    name: string;
    email: string;
    picture: string;
    is_superuser?: boolean;
    tenant_id?: string | null;
    roles?: string[];
  };
}

export default function Header({ user }: HeaderProps) {
  const { t } = useTranslation();

  // 根据用户角色决定权限管理页面的链接
  const getPermissionsLink = () => {
    if (!user) return "/admin";
    
    // 超级管理员 -> /admin
    if (user.is_superuser) {
      return "/admin";
    }
    // 租户管理员（拥有"管理员"角色）-> /tenant-admin
    if (user.roles && user.roles.includes("管理员")) {
      return "/tenant-admin";
    }
    // 普通用户没有权限管理入口，默认返回dashboard
    return "/dashboard";
  };

  // 判断是否显示权限管理链接
  const shouldShowPermissionsLink = () => {
    if (!user) return false;
    // 超级管理员或租户管理员才显示
    return user.is_superuser || (user.roles && user.roles.includes("管理员"));
  };

  const {
    value: isSyncModalOpen,
    setTrue: openSyncModal,
    setFalse: closeSyncModal,
  } = useBoolean(false);

  const {
    value: isMCPConnected,
    setTrue: setMCPConnected,
    setFalse: setMCPDisconnected,
  } = useBoolean(false);

  const handleDataSyncConfirm = () => {
    syncData()
      .finally(() => {
        closeSyncModal();
      });
  };

  useEffect(() => {
    const checkMCPConnection = () => {
      fetch.checkMCPHealth()
        .then(() => setMCPConnected())
        .catch(() => setMCPDisconnected());
    };

    checkMCPConnection();
    const interval = setInterval(checkMCPConnection, 30000);

    return () => clearInterval(interval);
  }, [setMCPConnected, setMCPDisconnected]);

  return (
    <>
      <header className="relative flex flex-row h-14 min-h-14 px-5 items-center justify-between w-full max-w-[1920px] mx-auto">
        <div className="flex flex-row gap-4 items-center">
          <CogneeIcon />
          <div className="text-lg">Cognee Local</div>
        </div>

        <div className="flex flex-row items-center gap-2.5">
          <Link href="/mcp-status" className="!text-indigo-600 pl-4 pr-4">
            <StatusDot className="mr-2" isActive={isMCPConnected} />
            {isMCPConnected ? t("instances.mcpConnected") : t("instances.mcpDisconnected")}
          </Link>
          {shouldShowPermissionsLink() && (
            <Link href={getPermissionsLink()} className="!text-indigo-600 pl-4 pr-4">
              权限管理
            </Link>
          )}
          <GhostButton onClick={openSyncModal} className="text-indigo-600 gap-3 pl-4 pr-4">
            <CloudIcon />
            <div>{t("navigation.sync")}</div>
          </GhostButton>
          <a href="/plan" className="!text-indigo-600 pl-4 pr-4">
            {t("navigation.premium")}
          </a>
          <a href="https://platform.cognee.ai" className="!text-indigo-600 pl-4 pr-4">{t("navigation.apiKeys")}</a>
          <LanguageSwitcher />
          {/* <div className="px-2 py-2 mr-3">
            <SettingsIcon />
          </div> */}
          <Link href="/account" className="bg-indigo-600 w-8 h-8 rounded-full overflow-hidden">
            {user?.picture ? (
              <Image width="32" height="32" alt="Name of the user" src={user.picture} />
            ) : (
              <div className="w-8 h-8 rounded-full text-white flex items-center justify-center">
                {user?.email?.charAt(0) || "C"}
              </div>
            )}
          </Link>
        </div>
      </header>

      <Modal isOpen={isSyncModalOpen}>
        <div className="w-full max-w-2xl">
          <div className="flex flex-row items-center justify-between">
            <span className="text-2xl">{t("sync.title")}</span>
            <IconButton onClick={closeSyncModal}><CloseIcon /></IconButton>
          </div>
          <div className="mt-8 mb-6">{t("sync.description")}</div>
          <div className="flex flex-row gap-4 mt-4 justify-end">
            <GhostButton type="button" onClick={closeSyncModal}>{t("common.cancel")}</GhostButton>
            <CTAButton onClick={handleDataSyncConfirm} type="submit">{t("common.confirm")}</CTAButton>
          </div>
        </div>
      </Modal>
    </>
  );
}
