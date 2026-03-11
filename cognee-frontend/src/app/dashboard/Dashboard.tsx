"use client";

import { useCallback, useRef, useState } from "react";

import { Header } from "@/ui/Layout";
import { SearchIcon } from "@/ui/Icons";
import { fetch } from "@/utils";
import { useAuthenticatedUser } from "@/modules/auth";
import { Dataset } from "@/modules/ingestion/useDatasets";

import AddDataToCognee from "./AddDataToCognee";
import DatasetsAccordion from "./DatasetsAccordion";

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

  // ############################
  // Datasets logic

  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const refreshDatasetsRef = useRef(() => {});
  const getDatasetDataRef = useRef<((datasetId: string) => Promise<any>) | undefined>();

  const handleDatasetsChange = useCallback((payload: { datasets: Dataset[], refreshDatasets: () => void, getDatasetData: (datasetId: string) => Promise<any> }) => {
    const {
      datasets,
      refreshDatasets,
      getDatasetData,
    } = payload;

    refreshDatasetsRef.current = refreshDatasets;
    getDatasetDataRef.current = getDatasetData;
    setDatasets(datasets);
  }, []);

  return (
    <div className="h-full flex flex-col">
      <Header user={user} />

      <div className="relative flex-1 flex flex-row gap-2.5 items-start w-full max-w-[1920px] max-h-[calc(100% - 3.5rem)] overflow-hidden mx-auto px-2.5 pb-2.5">
        <div className="px-5 py-4 lg:w-96 bg-white rounded-xl h-[calc(100%-2.75rem)]">
          <div className="relative mb-2">
            <label htmlFor="search-input"><SearchIcon className="absolute left-3 top-[10px] cursor-text" /></label>
            <input id="search-input" className="text-xs leading-3 w-full h-8 flex flex-row items-center gap-2.5 rounded-3xl pl-9 placeholder-gray-300 border-gray-300 border-[1px] focus:outline-indigo-600" placeholder="Search datasets..." />
          </div>

          <AddDataToCognee
            datasets={datasets}
            refreshDatasets={refreshDatasetsRef.current}
            getDatasetData={getDatasetDataRef.current}
          />

          <div className="mt-7">
            <DatasetsAccordion
              title={<span className="text-xs font-medium">数据集</span>}
              switchCaretPosition={true}
              className="pt-3 pb-1.5"
              contentClassName="pl-4"
              onDatasetsChange={handleDatasetsChange}
            />
          </div>
        </div>

        <div className="flex-1 flex flex-col justify-between h-full overflow-y-auto">
        </div>
      </div>
    </div>
  );
}
