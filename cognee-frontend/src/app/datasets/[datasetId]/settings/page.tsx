"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useTranslation } from "react-i18next";
import "@/i18n/i18n";
import renameDataset from "@/modules/datasets/renameDataset";
import {
  ShareGroup,
  DatasetShare,
  listMyGroups,
  shareDatasetWithGroup,
  revokeDatasetFromGroup,
  getDatasetShares,
} from "@/modules/sharing/api";

// ── Icons ─────────────────────────────────────────────────────────────────────

function BackIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
    </svg>
  );
}

function ExternalLinkIcon() {
  return (
    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
    </svg>
  );
}

// ── Tab type ──────────────────────────────────────────────────────────────────

type Tab = "basic" | "sharing";

// ── Sharing Tab ───────────────────────────────────────────────────────────────

interface SharingTabProps {
  datasetId: string;
}

function SharingTab({ datasetId }: SharingTabProps) {
  const { t } = useTranslation();
  const router = useRouter();
  const [groups, setGroups] = useState<ShareGroup[]>([]);
  const [shares, setShares] = useState<DatasetShare[]>([]);
  const [sharingGroupId, setSharingGroupId] = useState("");
  const [sharingPermission, setSharingPermission] = useState<"read" | "write">("read");
  const [sharing, setSharing] = useState(false);
  const [revoking, setRevoking] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [g, s] = await Promise.all([listMyGroups(), getDatasetShares(datasetId)]);
    setGroups(g);
    setShares(s);
    if (g.length > 0 && !sharingGroupId) {
      setSharingGroupId(g[0].id);
    }
  }, [datasetId, sharingGroupId]);

  useEffect(() => { load(); }, [load]);

  const handleShare = async () => {
    if (!sharingGroupId) return;
    setSharing(true);
    try {
      await shareDatasetWithGroup(sharingGroupId, datasetId, sharingPermission);
      await load();
    } finally {
      setSharing(false);
    }
  };

  const handleRevoke = async (groupId: string, groupName: string) => {
    if (!window.confirm(t("sharing.confirmRevokeShare", { name: groupName }))) return;
    setRevoking(groupId);
    try {
      await revokeDatasetFromGroup(groupId, datasetId);
      await load();
    } finally {
      setRevoking(null);
    }
  };

  const sharedGroupIds = new Set(shares.map((s) => s.group_id));
  const availableGroups = groups.filter((g) => !sharedGroupIds.has(g.id));

  return (
    <div className="space-y-6">
      {/* Hint: link to unified group management */}
      <div className="flex items-start gap-2 text-sm bg-blue-50 border border-blue-100 rounded-xl px-4 py-3">
        <span className="text-blue-500 mt-0.5">💡</span>
        <span className="text-gray-600">
          {t("sharing.manageGroupsHint")}{" "}
          <button
            onClick={() => router.push("/settings/sharing")}
            className="inline-flex items-center gap-1 text-indigo-600 hover:text-indigo-800 font-medium hover:underline transition-colors"
          >
            {t("sharing.manageGroupsLink")}
            <ExternalLinkIcon />
          </button>
        </span>
      </div>

      {/* Share this dataset with a group */}
      <section>
        <h3 className="text-sm font-semibold text-gray-700 mb-3">{t("sharing.sharedWith")}</h3>

        {groups.length === 0 ? (
          <p className="text-sm text-gray-400 py-4 text-center border border-dashed border-gray-200 rounded-xl">
            {t("sharing.noGroupsToShare")}{" "}
            <button
              onClick={() => router.push("/settings/sharing")}
              className="text-indigo-600 hover:underline font-medium"
            >
              {t("sharing.manageGroupsLink")}
            </button>
          </p>
        ) : availableGroups.length > 0 ? (
          <div className="flex items-center gap-3 mb-4 p-3 bg-gray-50 rounded-xl border border-gray-100">
            <select
              value={sharingGroupId}
              onChange={(e) => setSharingGroupId(e.target.value)}
              className="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-300 bg-white"
            >
              {availableGroups.map((g) => (
                <option key={g.id} value={g.id}>{g.name}</option>
              ))}
            </select>
            <select
              value={sharingPermission}
              onChange={(e) => setSharingPermission(e.target.value as "read" | "write")}
              className="px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-300 bg-white"
            >
              <option value="read">{t("sharing.permRead")}</option>
              <option value="write">{t("sharing.permWrite")}</option>
            </select>
            <button
              disabled={sharing || !sharingGroupId}
              onClick={handleShare}
              className="px-4 py-2 text-sm font-medium bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors whitespace-nowrap"
            >
              {sharing ? "…" : t("sharing.shareToGroup")}
            </button>
          </div>
        ) : null}

        {shares.length === 0 ? (
          <p className="text-sm text-gray-400 py-4 text-center border border-dashed border-gray-200 rounded-xl">
            {t("sharing.notShared")}
          </p>
        ) : (
          <ul className="space-y-2">
            {shares.map((s) => (
              <li key={s.group_id} className="flex items-center justify-between px-4 py-3 bg-gray-50 rounded-xl border border-gray-100">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-gray-800">{s.group_name}</span>
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                    s.permission_type === "write" ? "bg-purple-100 text-purple-700" : "bg-blue-100 text-blue-700"
                  }`}>
                    {s.permission_type === "write" ? t("sharing.permWrite") : t("sharing.permRead")}
                  </span>
                </div>
                <button
                  disabled={revoking === s.group_id}
                  onClick={() => handleRevoke(s.group_id, s.group_name)}
                  className="text-xs text-red-500 hover:text-red-700 disabled:opacity-50 transition-colors"
                >
                  {revoking === s.group_id ? "…" : t("sharing.revokeShare")}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

// ── Main Settings Page ────────────────────────────────────────────────────────

export default function DatasetSettingsPage() {
  const params = useParams();
  const router = useRouter();
  const { t } = useTranslation();
  const datasetId = params.datasetId as string;

  const [activeTab, setActiveTab] = useState<Tab>("basic");
  const [datasetName, setDatasetName] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/v1/datasets`, { credentials: "include" })
      .then((r) => r.json())
      .then((datasets: Array<{ id: string; name: string }>) => {
        const found = datasets.find((d) => d.id === datasetId);
        if (found) setDatasetName(found.name);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [datasetId]);

  const handleSave = async () => {
    if (!datasetName.trim()) return;
    setSaving(true);
    setSaveSuccess(false);
    try {
      await renameDataset(datasetId, datasetName.trim());
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err) {
      console.error("Rename failed", err);
      alert(t("sharing.saveError"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-3xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="flex items-center gap-3 mb-8">
          <button
            onClick={() => router.push("/dashboard")}
            className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 transition-colors"
          >
            <BackIcon />
            {t("sharing.backToDataset")}
          </button>
          <span className="text-gray-300">/</span>
          <h1 className="text-lg font-semibold text-gray-900">
            {loading ? "…" : datasetName} — {t("sharing.pageTitle")}
          </h1>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-white border border-gray-200 rounded-xl p-1 mb-6 w-fit">
          {(["basic", "sharing"] as Tab[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                activeTab === tab
                  ? "bg-indigo-600 text-white"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              {tab === "basic" ? t("sharing.tabBasic") : t("sharing.tabSharing")}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div className="bg-white rounded-2xl border border-gray-100 p-6 shadow-sm">
          {activeTab === "basic" && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                {t("sharing.datasetName")}
              </label>
              <div className="flex items-center gap-3">
                <input
                  type="text"
                  value={datasetName}
                  onChange={(e) => setDatasetName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSave()}
                  className="flex-1 px-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-300 transition-colors"
                  disabled={loading}
                />
                <button
                  disabled={saving || loading || !datasetName.trim()}
                  onClick={handleSave}
                  className="px-4 py-2 text-sm font-medium bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
                >
                  {saving ? "…" : t("sharing.save")}
                </button>
              </div>
              {saveSuccess && (
                <p className="mt-2 text-sm text-green-600">{t("sharing.saveSuccess")}</p>
              )}
            </div>
          )}

          {activeTab === "sharing" && (
            <SharingTab datasetId={datasetId} />
          )}
        </div>
      </div>
    </div>
  );
}
