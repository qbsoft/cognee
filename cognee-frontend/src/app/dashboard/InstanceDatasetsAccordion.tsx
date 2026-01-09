import classNames from "classnames";
import { useCallback, useEffect } from "react";
import { useTranslation } from "react-i18next";

import { fetch, isCloudEnvironment, useBoolean } from "@/utils";
import { checkCloudConnection } from "@/modules/cloud";
import { CaretIcon, CloseIcon, CloudIcon, LocalCogneeIcon } from "@/ui/Icons";
import { CTAButton, GhostButton, IconButton, Input, Modal } from "@/ui/elements";
import "@/i18n/i18n";

import DatasetsAccordion, { DatasetsAccordionProps } from "./DatasetsAccordion";

type InstanceDatasetsAccordionProps = Omit<DatasetsAccordionProps, "title">;

export default function InstanceDatasetsAccordion({ onDatasetsChange }: InstanceDatasetsAccordionProps) {
  const { t } = useTranslation();

  const {
    value: isLocalCogneeConnected,
    setTrue: setLocalCogneeConnected,
  } = useBoolean(false);

  const {
    value: isCloudCogneeConnected,
    setTrue: setCloudCogneeConnected,
  } = useBoolean(isCloudEnvironment());

  const checkConnectionToCloudCognee = useCallback((apiKey?: string) => {
    if (apiKey) {
      fetch.setApiKey(apiKey);
    }
    return checkCloudConnection()
      .then(setCloudCogneeConnected)
      .catch(() => {
        // Silently ignore cloud connection failures
        // This is expected when cloud service is not running
      });
  }, [setCloudCogneeConnected]);

  useEffect(() => {
    const checkConnectionToLocalCognee = () => {
      fetch.checkHealth()
        .then(setLocalCogneeConnected)
    };

    checkConnectionToLocalCognee();
    checkConnectionToCloudCognee();
  }, [checkConnectionToCloudCognee, setCloudCogneeConnected, setLocalCogneeConnected]);

  const {
    value: isCloudConnectedModalOpen,
    setTrue: openCloudConnectionModal,
    setFalse: closeCloudConnectionModal,
  } = useBoolean(false);

  const handleCloudConnectionConfirm = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const apiKeyValue = event.currentTarget.apiKey.value;

    checkConnectionToCloudCognee(apiKeyValue)
      .then(() => {
        closeCloudConnectionModal();
      });
  };

  const isCloudEnv = isCloudEnvironment();

  return (
    <div className={classNames("flex flex-col", {
      "flex-col-reverse": isCloudEnv,
    })}>
      <DatasetsAccordion
        title={(
          <div className="flex flex-row items-center justify-between">
            <div className="flex flex-row items-center gap-2">
              <LocalCogneeIcon className="text-indigo-700" />
              <span className="text-xs">{t("instances.localCognee")}</span>
            </div>
          </div>
        )}
        tools={isLocalCogneeConnected ? <span className="text-xs text-indigo-600">{t("common.connected")}</span> : <span className="text-xs text-gray-400">{t("common.notConnected")}</span>}
        switchCaretPosition={true}
        className="pt-3 pb-1.5"
        contentClassName="pl-4"
        onDatasetsChange={!isCloudEnv ? onDatasetsChange : () => { }}
      />

      {isCloudCogneeConnected ? (
        <DatasetsAccordion
          title={(
            <div className="flex flex-row items-center justify-between">
              <div className="flex flex-row items-center gap-2">
                <LocalCogneeIcon className="text-indigo-700" />
                <span className="text-xs">{t("instances.cloudCognee")}</span>
              </div>
            </div>
          )}
          tools={<span className="text-xs text-indigo-600">{t("common.connected")}</span>}
          switchCaretPosition={true}
          className="pt-3 pb-1.5"
          contentClassName="pl-4"
          onDatasetsChange={isCloudEnv ? onDatasetsChange : () => { }}
          useCloud={true}
        />
      ) : (
        <button className="w-full flex flex-row items-center justify-between py-1.5 cursor-pointer pt-3" onClick={!isCloudCogneeConnected ? openCloudConnectionModal : () => { }}>
          <div className="flex flex-row items-center gap-1.5">
            <CaretIcon className="rotate-[-90deg]" />
            <div className="flex flex-row items-center gap-2">
              <CloudIcon color="#000000" />
              <span className="text-xs">{t("instances.cloudCognee")}</span>
            </div>
          </div>
          <span className="text-xs text-gray-400">{t("common.notConnected")}</span>
        </button>
      )}

      <Modal isOpen={isCloudConnectedModalOpen}>
        <div className="w-full max-w-2xl">
          <div className="flex flex-row items-center justify-between">
            <span className="text-2xl">{t("cloud.connectTitle")}</span>
            <IconButton onClick={closeCloudConnectionModal}><CloseIcon /></IconButton>
          </div>
          <div className="mt-8 mb-6">{t("cloud.apiKeyPrompt")} <a className="!text-indigo-600" href="https://platform.cognee.ai">{t("cloud.ourPlatform")}</a></div>
          <form onSubmit={handleCloudConnectionConfirm}>
            <div className="max-w-md">
              <Input name="apiKey" type="text" placeholder={t("cloud.apiKeyPlaceholder")} required />
            </div>
            <div className="flex flex-row gap-4 mt-4 justify-end">
              <GhostButton type="button" onClick={() => closeCloudConnectionModal()}>{t("common.cancel")}</GhostButton>
              <CTAButton type="submit">{t("common.connect")}</CTAButton>
            </div>
          </form>
        </div>
      </Modal>
    </div>
  );
}
