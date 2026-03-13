"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import { SettingsIcon } from "../Icons";
import { useOutsideClick } from "@/utils";

interface SettingsDropdownProps {
  user?: {
    is_superuser?: boolean;
    roles?: string[];
  };
}

export default function SettingsDropdown({ user }: SettingsDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);

  const close = useCallback(() => setIsOpen(false), []);
  const dropdownRef = useOutsideClick<HTMLDivElement>(close, isOpen);

  const getPermissionsLink = () => {
    if (!user) return "/admin";
    if (user.is_superuser) return "/admin";
    if (user.roles && user.roles.includes("\u7ba1\u7406\u5458")) return "/tenant-admin";
    return null;
  };

  const shouldShowPermissions =
    user?.is_superuser || (user?.roles && user.roles.includes("\u7ba1\u7406\u5458"));

  const permissionsLink = getPermissionsLink();

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen((prev) => !prev)}
        className="p-2 rounded-lg text-gray-500 hover:text-gray-700 hover:bg-gray-100 transition-colors"
        aria-label="Settings"
      >
        <SettingsIcon />
      </button>

      {isOpen && (
        <div className="absolute right-0 top-full mt-2 w-48 bg-white rounded-xl shadow-lg z-50 py-1 border border-gray-200">
          <Link
            href="/settings/models"
            className="block px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
            onClick={close}
          >
            {"\u6a21\u578b\u914d\u7f6e"}
          </Link>
          <Link
            href="/settings/sharing"
            className="block px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
            onClick={close}
          >
            {"\u5171\u4eab\u7ec4\u7ba1\u7406"}
          </Link>
          {shouldShowPermissions && permissionsLink && (
            <Link
              href={permissionsLink}
              className="block px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
              onClick={close}
            >
              {"\u6743\u9650\u7ba1\u7406"}
            </Link>
          )}
        </div>
      )}
    </div>
  );
}
