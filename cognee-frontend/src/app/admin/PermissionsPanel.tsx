"use client";

import { useState } from "react";
import { CTAButton, Input } from "@/ui/elements";
import { fetch } from "@/utils";
import { useTranslation } from "react-i18next";

export default function PermissionsPanel() {
  const { t } = useTranslation();
  const [principalId, setPrincipalId] = useState("");
  const [datasetIds, setDatasetIds] = useState("");
  const [permissionType, setPermissionType] = useState("read");
  const [isGranting, setIsGranting] = useState(false);

  const handleGrantPermission = async () => {
    if (!principalId.trim() || !datasetIds.trim()) return;

    setIsGranting(true);
    try {
      const datasetIdArray = datasetIds.split(",").map((id) => id.trim());
      const formData = new URLSearchParams();
      formData.append("permission_name", permissionType);
      formData.append("dataset_ids", JSON.stringify(datasetIdArray));

      await fetch(`/v1/permissions/datasets/${principalId}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: formData.toString(),
      });

      alert(t("admin.permissions.grantSuccess"));
      setPrincipalId("");
      setDatasetIds("");
    } catch (error) {
      console.error("Grant permission failed:", error);
      alert(t("admin.permissions.grantError"));
    } finally {
      setIsGranting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-gray-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-4">{t("admin.permissions.title")}</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">
              {t("admin.permissions.principalIdLabel")}
            </label>
            <Input
              type="text"
              placeholder={t("admin.permissions.principalIdPlaceholder")}
              value={principalId}
              onChange={(e) => setPrincipalId(e.target.value)}
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">
              {t("admin.permissions.datasetIdLabel")}
            </label>
            <Input
              type="text"
              placeholder={t("admin.permissions.datasetIdPlaceholder")}
              value={datasetIds}
              onChange={(e) => setDatasetIds(e.target.value)}
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">{t("admin.permissions.permissionTypeLabel")}</label>
            <select
              value={permissionType}
              onChange={(e) => setPermissionType(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-600"
            >
              <option value="read">{t("admin.permissions.optionRead")}</option>
              <option value="write">{t("admin.permissions.optionWrite")}</option>
              <option value="delete">{t("admin.permissions.optionDelete")}</option>
              <option value="share">{t("admin.permissions.optionShare")}</option>
            </select>
          </div>

          <CTAButton
            onClick={handleGrantPermission}
            disabled={isGranting || !principalId.trim() || !datasetIds.trim()}
            className="w-full"
          >
            {isGranting ? t("admin.permissions.assigning") : t("admin.permissions.assignButton")}
          </CTAButton>
        </div>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="font-semibold mb-2">{t("admin.permissions.usageTitle")}</h4>
        <ul className="text-sm text-gray-700 space-y-1">
          <li>• {t("admin.permissions.usage1")}</li>
          <li>• {t("admin.permissions.usage2")}</li>
          <li>• {t("admin.permissions.usage3")}</li>
          <li>• {t("admin.permissions.usage4")}</li>
          <li>• {t("admin.permissions.usage5")}</li>
          <li>• {t("admin.permissions.usage6")}</li>
          <li>• {t("admin.permissions.usage7")}</li>
        </ul>
      </div>
    </div>
  );
}
