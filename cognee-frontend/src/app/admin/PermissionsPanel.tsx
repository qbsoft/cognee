"use client";

import { useState } from "react";
import { CTAButton, Input } from "@/ui/elements";
import { fetch } from "@/utils";

export default function PermissionsPanel() {
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

      alert("权限分配成功！");
      setPrincipalId("");
      setDatasetIds("");
    } catch (error) {
      console.error("分配权限失败:", error);
      alert("分配权限失败，请检查输入的ID是否正确");
    } finally {
      setIsGranting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-gray-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-4">分配数据集权限</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">
              Principal ID（用户ID 或 角色ID）
            </label>
            <Input
              type="text"
              placeholder="粘贴用户或角色的UUID"
              value={principalId}
              onChange={(e) => setPrincipalId(e.target.value)}
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">
              数据集 ID（多个用逗号分隔）
            </label>
            <Input
              type="text"
              placeholder="例如: uuid1, uuid2, uuid3"
              value={datasetIds}
              onChange={(e) => setDatasetIds(e.target.value)}
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">权限类型</label>
            <select
              value={permissionType}
              onChange={(e) => setPermissionType(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-600"
            >
              <option value="read">Read - 读取数据</option>
              <option value="write">Write - 写入数据</option>
              <option value="delete">Delete - 删除数据</option>
              <option value="share">Share - 分享权限</option>
            </select>
          </div>

          <CTAButton
            onClick={handleGrantPermission}
            disabled={isGranting || !principalId.trim() || !datasetIds.trim()}
            className="w-full"
          >
            {isGranting ? "分配中..." : "分配权限"}
          </CTAButton>
        </div>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="font-semibold mb-2">💡 使用说明</h4>
        <ul className="text-sm text-gray-700 space-y-1">
          <li>• 从"用户管理"或"角色管理"面板复制 Principal ID</li>
          <li>• 从 Dashboard 的 Datasets 面板查看数据集 ID</li>
          <li>• 权限继承顺序：用户权限 → 角色权限 → 租户权限</li>
          <li>• Read: 可查询和可视化数据</li>
          <li>• Write: 可添加、修改数据</li>
          <li>• Delete: 可删除整个数据集</li>
          <li>• Share: 可将权限分享给其他用户</li>
        </ul>
      </div>
    </div>
  );
}
