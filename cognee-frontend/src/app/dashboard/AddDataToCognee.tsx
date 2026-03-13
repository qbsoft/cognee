import { FormEvent, useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useRouter } from "next/navigation";

import { LoadingIndicator } from "@/ui/App";
import { useModal } from "@/ui/elements/Modal";
import { CloseIcon, MinusIcon, PlusIcon } from "@/ui/Icons";
import { CTAButton, GhostButton, IconButton, Modal, NeutralButton, Select } from "@/ui/elements";
import "@/i18n/i18n";

import addData from "@/modules/ingestion/addData";
import { Dataset } from "@/modules/ingestion/useDatasets";
import cognifyDataset from "@/modules/datasets/cognifyDataset";

const NEW_DATASET_VALUE = "__new__";

interface AddDataToCogneeProps {
  datasets: Dataset[];
  refreshDatasets: () => void;
  getDatasetData?: (datasetId: string) => Promise<any>;
  useCloud?: boolean;
  ctaLabel?: string;
}

export default function AddDataToCognee({ datasets, refreshDatasets, getDatasetData, useCloud = false, ctaLabel }: AddDataToCogneeProps) {
  const { t } = useTranslation();
  const router = useRouter();
  const [filesForUpload, setFilesForUpload] = useState<File[]>([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>(
    datasets.length ? datasets[0].id : NEW_DATASET_VALUE
  );
  const [newDatasetName, setNewDatasetName] = useState<string>("");

  // sync default selection if datasets list changes (e.g. after modal opens)
  useEffect(() => {
    if (!datasets.length) {
      setSelectedDatasetId(NEW_DATASET_VALUE);
    }
  }, [datasets.length]);

  const addFiles = useCallback((event: FormEvent<HTMLInputElement>) => {
    const formElements = event.currentTarget;
    const newFiles = formElements.files;

    if (newFiles?.length) {
      setFilesForUpload((oldFiles) => [...oldFiles, ...Array.from(newFiles)]);
    }
  }, []);

  const removeFile = useCallback((file: File) => {
    setFilesForUpload((oldFiles) => oldFiles.filter((f) => f !== file));
  }, []);

  const processDataWithCognee = useCallback((state?: object, event?: FormEvent<HTMLFormElement>) => {
    event!.preventDefault();

    if (!filesForUpload) {
      return;
    }

    const isNew = selectedDatasetId === NEW_DATASET_VALUE;
    const datasetArg = isNew
      ? { name: newDatasetName.trim() || "main_dataset" }
      : { id: selectedDatasetId };

    return addData(
      datasetArg,
      filesForUpload,
      useCloud
    )
      .then(async ({ dataset_id, dataset_name }) => {
        // Refresh datasets list
        await refreshDatasets();
        
        // Refresh the specific dataset's data to show newly added items
        if (getDatasetData) {
          await getDatasetData(dataset_id);
        }

        return cognifyDataset(
          {
            id: dataset_id,
            name: dataset_name,
            data: [],  // not important, just to mimick Dataset
            status: "",  // not important, just to mimick Dataset
          },
          useCloud,
        )
          .then(() => {
            setFilesForUpload([]);
            // 跳转到数据集详情页，自动轮询处理进度
            router.push(`/datasets/${dataset_id}?processing=true`);
          });
      })
      .catch((error) => {
        console.error("Error adding data:", error);
        alert(`Failed to add data: ${error.message}`);
        throw error;
      });
  }, [filesForUpload, refreshDatasets, useCloud, router, selectedDatasetId, newDatasetName]);

  const {
    isModalOpen: isAddDataModalOpen,
    openModal: openAddDataModal,
    closeModal: closeAddDataModal,
    isActionLoading: isProcessingDataWithCognee,
    confirmAction: submitDataToCognee,
  } = useModal(false, processDataWithCognee);

  return (
    <>
      {ctaLabel ? (
        <button
          onClick={openAddDataModal}
          className="inline-flex items-center gap-2 px-6 py-3 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-xl transition-colors shadow-sm"
        >
          <PlusIcon />
          {ctaLabel}
        </button>
      ) : (
        <button
          onClick={openAddDataModal}
          className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white text-sm font-medium rounded-lg transition-colors shadow-sm whitespace-nowrap"
        >
          <PlusIcon color="white" />
          {t("navigation.addData")}
        </button>
      )}

      <Modal isOpen={isAddDataModalOpen}>
        <div className="w-full max-w-2xl">
          <div className="flex flex-row items-center justify-between">
            <span className="text-2xl">{t("datasets.addDataTitle")}</span>
            <IconButton disabled={isProcessingDataWithCognee} onClick={closeAddDataModal}><CloseIcon /></IconButton>
          </div>
          <div className="mt-8 mb-6">{useCloud ? t("datasets.addDataDescCloud") : t("datasets.addDataDescLocal")}</div>
          <form onSubmit={submitDataToCognee}>
            <div className="max-w-md flex flex-col gap-4">
              <Select
                value={selectedDatasetId}
                name="datasetName"
                onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setSelectedDatasetId(e.target.value)}
              >
                <option value={NEW_DATASET_VALUE}>＋ {t("datasets.newDataset")}</option>
                {datasets.map((dataset: Dataset) => (
                  <option key={dataset.id} value={dataset.id}>{dataset.name}</option>
                ))}
              </Select>

              {selectedDatasetId === NEW_DATASET_VALUE && (
                <input
                  type="text"
                  value={newDatasetName}
                  onChange={(e) => setNewDatasetName(e.target.value)}
                  placeholder={t("datasets.datasetNamePlaceholder")}
                  className="w-full px-4 py-2 rounded-lg border border-gray-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-300 transition-colors"
                />
              )}

              <NeutralButton className="w-full relative justify-start pl-4">
                <input onChange={addFiles} required name="files" tabIndex={-1} type="file" multiple className="absolute w-full h-full cursor-pointer opacity-0" />
                <span>{t("datasets.selectFiles")}</span>
              </NeutralButton>

              {!!filesForUpload.length && (
                <div className="pt-4 mt-4 border-t-1 border-t-gray-100">
                  <div className="mb-1.5">{t("datasets.selectedFiles")}</div>
                  {filesForUpload.map((file) => (
                    <div key={file.name} className="py-1.5 pl-2 flex flex-row items-center justify-between w-full">
                      <span className="text-sm">{file.name}</span>
                      <IconButton onClick={removeFile.bind(null, file)}><MinusIcon /></IconButton>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="flex flex-row gap-4 mt-4 justify-end">
              <GhostButton disabled={isProcessingDataWithCognee} type="button" onClick={() => closeAddDataModal()}>{t("common.cancel")}</GhostButton>
              <CTAButton disabled={isProcessingDataWithCognee} type="submit">
                {isProcessingDataWithCognee && <LoadingIndicator color="white" />}
                {t("common.add")}
              </CTAButton>
            </div>
          </form>
        </div>
      </Modal>
    </>
  );
}
