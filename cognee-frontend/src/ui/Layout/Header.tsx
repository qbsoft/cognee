"use client";

import Link from "next/link";
import Image from "next/image";
import { useTranslation } from "react-i18next";
import { CogneeIcon } from "../Icons";
import SettingsDropdown from "./SettingsDropdown";

const TABS = [
  { id: "datasets", tKey: "tabs.datasets" },
  { id: "graph", tKey: "tabs.graph" },
  { id: "search", tKey: "tabs.search" },
  { id: "api", tKey: "tabs.api" },
];

interface HeaderProps {
  user?: {
    name: string;
    email: string;
    picture: string;
    is_superuser?: boolean;
    tenant_id?: string | null;
    roles?: string[];
  };
  activeTab?: string;
  onTabChange?: (tab: string) => void;
}

export default function Header({ user, activeTab, onTabChange }: HeaderProps) {
  const { t } = useTranslation();

  return (
    <header className="relative flex flex-row h-14 min-h-14 px-5 items-center justify-between w-full max-w-[1920px] mx-auto border-b border-gray-200">
      {/* Left: Logo */}
      <div className="flex flex-row gap-3 items-center">
        <CogneeIcon />
        <span className="text-lg font-semibold text-gray-900">Cognee</span>
      </div>

      {/* Center: Tab navigation (only shown when activeTab/onTabChange provided) */}
      {onTabChange ? (
        <nav className="flex flex-row gap-1 items-center">
          {TABS.map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => onTabChange(tab.id)}
                className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-indigo-50 text-indigo-700"
                    : "text-gray-600 hover:text-gray-900 hover:bg-gray-50"
                }`}
              >
                {t(tab.tKey)}
              </button>
            );
          })}
        </nav>
      ) : (
        <div />
      )}

      {/* Right: Settings + Avatar */}
      <div className="flex flex-row items-center gap-2">
        <SettingsDropdown user={user} />
        <Link href="/account" className="bg-indigo-600 w-8 h-8 rounded-full overflow-hidden flex-shrink-0">
          {user?.picture ? (
            <Image width="32" height="32" alt="User avatar" src={user.picture} />
          ) : (
            <div className="w-8 h-8 rounded-full text-white flex items-center justify-center text-sm font-medium">
              {user?.email?.charAt(0)?.toUpperCase() || "C"}
            </div>
          )}
        </Link>
      </div>
    </header>
  );
}
