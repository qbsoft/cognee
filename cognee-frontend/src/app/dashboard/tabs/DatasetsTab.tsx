"use client";

import { useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import { useTranslation } from "react-i18next";
import { SearchIcon, DatasetIcon } from "@/ui/Icons";
import { Dataset } from "@/modules/ingestion/useDatasets";
import AddDataToCognee from "../AddDataToCognee";

interface DatasetsTabProps {
  datasets: Dataset[];
  refreshDatasets: () => void;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  getDatasetData?: (datasetId: string) => Promise<any>;
}

type StatusInfo = {
  labelKey: string;
  className: string;
};

const PIPELINE_STAGES = ["parsing", "chunking", "graph_indexing", "vector_indexing"] as const;

function getDatasetStatus(dataset: Dataset): StatusInfo {
  const files = dataset.data;

  if (!files || files.length === 0) {
    return { labelKey: "dashboard.datasets.status.empty", className: "bg-gray-100 text-gray-600" };
  }

  let hasInProgress = false;
  let hasFailed = false;
  let allCompleted = true;

  for (const file of files) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const ps = (file as any).pipeline_status;
    if (!ps) {
      allCompleted = false;
      continue;
    }
    for (const stage of PIPELINE_STAGES) {
      const status = ps[stage]?.status;
      if (status === "in_progress" || status === "pending") {
        hasInProgress = true;
        allCompleted = false;
      } else if (status === "failed") {
        hasFailed = true;
        allCompleted = false;
      } else if (status !== "completed") {
        allCompleted = false;
      }
    }
  }

  if (hasFailed) {
    return { labelKey: "dashboard.datasets.status.failed", className: "bg-red-100 text-red-700" };
  }
  if (hasInProgress) {
    return { labelKey: "dashboard.datasets.status.inProgress", className: "bg-blue-100 text-blue-700" };
  }
  if (allCompleted) {
    return { labelKey: "dashboard.datasets.status.ready", className: "bg-green-100 text-green-700" };
  }
  return { labelKey: "dashboard.datasets.status.pending", className: "bg-yellow-100 text-yellow-700" };
}

export default function DatasetsTab({ datasets, refreshDatasets, getDatasetData }: DatasetsTabProps) {
  const { t } = useTranslation();
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState("");

  const filteredDatasets = useMemo(() => {
    if (!searchQuery.trim()) return datasets;
    const query = searchQuery.trim().toLowerCase();
    return datasets.filter((ds) => ds.name.toLowerCase().includes(query));
  }, [datasets, searchQuery]);

  return (
    <div className="space-y-4">
      {/* Search bar + Add data */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-md">
          <div className="absolute inset-y-0 left-3 flex items-center pointer-events-none text-gray-400">
            <SearchIcon />
          </div>
          <input
            type="text"
            placeholder={t("dashboard.datasets.searchPlaceholder")}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 rounded-lg border border-gray-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-300 transition-colors"
          />
        </div>
        <AddDataToCognee
          datasets={datasets}
          refreshDatasets={refreshDatasets}
          getDatasetData={getDatasetData}
        />
      </div>

      {/* Card grid or empty state */}
      {filteredDatasets.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-gray-400">
          <DatasetIcon />
          <p className="mt-3 text-sm">
            {datasets.length === 0
              ? t("dashboard.datasets.empty")
              : t("dashboard.datasets.noMatch")}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filteredDatasets.map((dataset) => {
            const status = getDatasetStatus(dataset);
            const fileCount = dataset.data?.length ?? 0;

            return (
              <div
                key={dataset.id}
                onClick={() => router.push(`/datasets/${dataset.id}`)}
                className="bg-white rounded-xl border border-gray-100 p-4 hover:shadow-md hover:border-indigo-200 transition-all cursor-pointer"
              >
                <div className="flex items-start justify-between mb-3">
                  <h3 className="text-sm font-medium text-gray-900 truncate flex-1 mr-2">
                    {dataset.name}
                  </h3>
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium whitespace-nowrap ${status.className}`}>
                    {t(status.labelKey)}
                  </span>
                </div>

                <p className="text-xs text-gray-500 mb-4">
                  {t("dashboard.datasets.fileCount", { count: fileCount })}
                </p>

                <div className="flex items-center justify-end">
                  <span className="text-xs text-indigo-500 font-medium hover:text-indigo-700 transition-colors">
                    {t("dashboard.datasets.queryLink")}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
