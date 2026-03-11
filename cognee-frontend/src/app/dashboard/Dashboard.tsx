"use client";

import { useCallback, useRef, useState } from "react";

import { Header } from "@/ui/Layout";
import { fetch } from "@/utils";
import { useAuthenticatedUser } from "@/modules/auth";
import { Dataset } from "@/modules/ingestion/useDatasets";

import DatasetsAccordion from "./DatasetsAccordion";
import { DatasetsTab, GraphTab, SearchTab, ApiTab } from "./tabs";

interface DashboardProps {
  user?: {
    id: string;
    name: string;
    email: string;
    picture: string;
  };
  accessToken: string;
}

export default function Dashboard({ accessToken }: DashboardProps) {
  fetch.setAccessToken(accessToken);
  const { user } = useAuthenticatedUser();

  // Tab state
  const [activeTab, setActiveTab] = useState("datasets");

  // Datasets logic (shared with DatasetsTab)
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const refreshDatasetsRef = useRef(() => {});
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const getDatasetDataRef = useRef<((datasetId: string) => Promise<any>) | undefined>();

  const handleDatasetsChange = useCallback(
    (payload: {
      datasets: Dataset[];
      refreshDatasets: () => void;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      getDatasetData: (datasetId: string) => Promise<any>;
    }) => {
      const { datasets, refreshDatasets, getDatasetData } = payload;
      refreshDatasetsRef.current = refreshDatasets;
      getDatasetDataRef.current = getDatasetData;
      setDatasets(datasets);
    },
    []
  );

  const renderActiveTab = () => {
    switch (activeTab) {
      case "datasets":
        return (
          <DatasetsTab
            datasets={datasets}
            refreshDatasets={refreshDatasetsRef.current}
            getDatasetData={getDatasetDataRef.current}
          />
        );
      case "graph":
        return <GraphTab />;
      case "search":
        return <SearchTab />;
      case "api":
        return <ApiTab />;
      default:
        return null;
    }
  };

  return (
    <div className="h-full flex flex-col bg-gray-50">
      <Header user={user} activeTab={activeTab} onTabChange={setActiveTab} />

      {/* Hidden datasets data source — drives DatasetsTab */}
      <div className="hidden">
        <DatasetsAccordion
          title={<span>datasets</span>}
          onDatasetsChange={handleDatasetsChange}
        />
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-hidden">{renderActiveTab()}</div>
    </div>
  );
}
