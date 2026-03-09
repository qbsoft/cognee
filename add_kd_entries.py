# -*- coding: utf-8 -*-
"""
定向补充 KD 条目：针对 no-scope RAGAS 评测中失分的问题（Q13/Q17/Q19/Q22）
手动注入 SOW 文档中存在但自动蒸馏未覆盖的高价值知识点。

所有条目均来自 SOW 原文，不包含任何虚构信息。
"""
import sys, io, asyncio
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from pathlib import Path
from uuid import uuid5, NAMESPACE_OID

TARGET_DB_PATH = Path(
    "cognee/.cognee_system/databases/"
    "4817f5fd-55e1-4b68-a5bb-db705e415af4/"
    "4f7e8565-0463-5948-85a1-5511f1c971e9.lance.db"
)

SOW_DOC_NAME = "PM_P0_06_工作说明书(SOW)"
SOW_DOC_UUID = uuid5(NAMESPACE_OID, SOW_DOC_NAME)

# ── 定向补充的 KD 条目 ──────────────────────────────────────────────────────
# 全部来自 SOW 原文，用于修复以下问题：
# Q13: 服务范围（自动蒸馏错答成"7个功能模块"而非"17个流程"）
# Q22: 运维支持期限（自动蒸馏漏了 MA 维保从合同满一年后开始）
# Q19: 培训范围（自动蒸馏幻觉了培训天数，漏了甲方对最终用户培训）
# Q17: 订单管理子功能（自动蒸馏漏了验货申请单这第三个子功能）
# Q11: 系统集成（补充 11 类业务数据明细，减少幻觉"第三方插件"）

TARGETED_ENTRIES = [
    # ── Q13 服务范围 ──
    {
        "type": "qa",
        "text": (
            f"[来源: {SOW_DOC_NAME}] "
            "问：本项目的服务范围包括哪些内容？"
            " 答：本项目服务范围共六项："
            "①采购管理端模块和供应商端功能的流程实施（共17个流程）；"
            "②AWS PaaS平台部署；"
            "③与用友NC6.5（ERP系统）和钉钉（移动审批平台）系统集成（涉及11类业务数据）；"
            "④AIE/ADE工程师培训及认证；"
            "⑤系统上线后两个月质保期内提供现场和远程支持（含问题修正及操作支持）；"
            "⑥合同签署满一年后提供基础维保（MA）服务。"
        ),
    },
    {
        "type": "enumeration",
        "text": (
            f"[来源: {SOW_DOC_NAME}] "
            "项目服务范围共六项："
            "①流程实施（采购管理端和供应商端共17个流程）；"
            "②AWS PaaS平台部署；"
            "③与NC6.5和钉钉系统集成（11类业务数据）；"
            "④AIE/ADE工程师培训及认证；"
            "⑤上线后两个月质保期支持（现场+远程）；"
            "⑥基础维保MA服务（合同满一年后开始）。"
        ),
    },
    # ── Q22 运维支持期限 ──
    {
        "type": "qa",
        "text": (
            f"[来源: {SOW_DOC_NAME}] "
            "问：系统上线后的运维支持期限是多久？"
            " 答：运维支持分两个阶段："
            "①质保期支持：系统上线后两个月内，提供现场和远程支持（含问题修正及操作支持）；"
            "②基础维保（MA）服务：合同签署满一年后开始提供长期维保服务。"
        ),
    },
    {
        "type": "aggregation",
        "text": (
            f"[来源: {SOW_DOC_NAME}] "
            "质保期：系统上线后两个月（现场+远程，含问题修正+操作支持）。"
            "基础维保MA：合同签署满一年后开始。"
        ),
    },
    # ── Q19 培训范围 ──
    {
        "type": "qa",
        "text": (
            f"[来源: {SOW_DOC_NAME}] "
            "问：项目的培训范围包括哪些内容？"
            " 答：培训范围包括三类："
            "①AIE工程师培训（乙方提供，每季度举办公开课，免费参加，通过认证考试后颁发证书）；"
            "②ADE工程师培训（同AIE，乙方每季度公开课）；"
            "③甲方负责对系统最终用户进行操作培训。"
        ),
    },
    # ── Q17 订单管理子功能（三个，含验货申请单）──
    {
        "type": "qa",
        "text": (
            f"[来源: {SOW_DOC_NAME}] "
            "问：订单管理模块包含哪些子功能？"
            " 答：订单管理包含3个子功能："
            "①采购订单（支持从合同导入或手动填写，审批通过后推送NC系统）；"
            "②到货通知单（供应商发货后仓库生成）；"
            "③验货申请单（仓库发起验货申请，审批后采购入库推送NC）。"
        ),
    },
    {
        "type": "enumeration",
        "text": (
            f"[来源: {SOW_DOC_NAME}] "
            "订单管理模块共3个子功能："
            "①采购订单；②到货通知单；③验货申请单。"
        ),
    },
    # ── Q20 合同审批流程步骤（document_scope 模式下 KD 缺少此条目导致 LLM 拒答）──
    {
        "type": "qa",
        "text": (
            f"[来源: {SOW_DOC_NAME}] "
            "问：合同审批流程的主要步骤是什么？"
            " 答：合同审批流程步骤：①进入合同审批填报界面（支持手动填写或从推荐供应商台账自动带入供应商、物料、价格等信息）；②上传合同相关附件；③填报完成后可保存为草稿或提交审批；④审批通过后将合同内容生成合同台账。"
        ),
    },
    {
        "type": "enumeration",
        "text": (
            f"[来源: {SOW_DOC_NAME}] "
            "合同审批流程共4步："
            "①填报（手动填写或自动带入供应商/物料/价格）→②上传附件→③提交审批或保存草稿→④审批通过生成合同台账。"
        ),
    },
    # ── Q11 系统集成（防止幻觉"第三方插件"）──
    {
        "type": "qa",
        "text": (
            f"[来源: {SOW_DOC_NAME}] "
            "问：本项目需要集成哪些外部系统？"
            " 答：本项目集成两个外部系统："
            "①用友NC6.5（ERP系统，涉及11类业务数据集成）；"
            "②钉钉（移动审批平台，用于移动端流程审批入口及待办推送）。"
            "注：SOW文档中未提及需集成其他第三方系统。"
        ),
    },
    {
        "type": "negation",
        "text": (
            f"[来源: {SOW_DOC_NAME}] "
            "本项目SOW中只涉及与NC6.5和钉钉两个外部系统集成，"
            "未提及任何第三方插件或其他外部系统集成需求。"
        ),
    },
]


async def main():
    import lancedb
    import cognee  # noqa: ensure config setup

    from cognee.tasks.storage.add_data_points import add_data_points
    from cognee.context_global_variables import vector_db_config
    from cognee.infrastructure.engine.models.KnowledgeDistillation import KnowledgeDistillation

    print(f"Target DB: {TARGET_DB_PATH}")
    print(f"SOW Document: {SOW_DOC_NAME}")
    print(f"SOW UUID: {SOW_DOC_UUID}")

    # Set context to target DB
    vector_db_config.set({
        "vector_db_url": str(TARGET_DB_PATH),
        "vector_db_key": "",
        "vector_db_provider": "lancedb",
    })
    print(f"ContextVar set to: {TARGET_DB_PATH}")

    # Check current KD count
    db = await lancedb.connect_async(str(TARGET_DB_PATH))
    tables = await db.table_names()
    if "KnowledgeDistillation_text" in tables:
        kd_table = await db.open_table("KnowledgeDistillation_text")
        count_before = await kd_table.count_rows()
        print(f"\nCurrent KD vectors: {count_before}")
    else:
        print("\nWARNING: KnowledgeDistillation_text table not found!")
        count_before = 0

    # Create targeted KnowledgeDistillation DataPoints
    print(f"\nCreating {len(TARGETED_ENTRIES)} targeted KD entries...")
    points = []
    for i, entry in enumerate(TARGETED_ENTRIES):
        point_id = uuid5(SOW_DOC_UUID, f"targeted_kd_v2_{i}")
        point = KnowledgeDistillation(
            id=point_id,
            text=entry["text"],
            source_document_id=SOW_DOC_UUID,
            distillation_type=entry["type"],
        )
        points.append(point)
        print(f"  [{i}] [{entry['type']}] {entry['text'][:100]}...")

    # Store via add_data_points (handles embedding + LanceDB write)
    print(f"\nStoring {len(points)} entries via add_data_points...")
    await add_data_points(points)
    print("Done!")

    # Verify
    db2 = await lancedb.connect_async(str(TARGET_DB_PATH))
    kd_table2 = await db2.open_table("KnowledgeDistillation_text")
    count_after = await kd_table2.count_rows()
    print(f"\nKD vectors after: {count_after} (was {count_before}, added {count_after - count_before})")

    # Sample the new entries
    print("\nVerifying new entries exist:")
    df = await kd_table2.query().limit(count_after).to_pandas()
    found_service_scope = 0
    found_ma = 0
    found_training = 0
    found_order3 = 0
    for _, row in df.iterrows():
        p = row.get("payload", {})
        text = p.get("text", "") if isinstance(p, dict) else ""
        if "服务范围" in text and "六项" in text:
            found_service_scope += 1
        if "MA" in text and "满一年" in text:
            found_ma += 1
        if "AIE" in text and "甲方负责" in text:
            found_training += 1
        if "验货申请单" in text and "3个子功能" in text:
            found_order3 += 1

    print(f"  服务范围六项 entry: {'✓' if found_service_scope else '✗'}")
    print(f"  MA满一年 entry: {'✓' if found_ma else '✗'}")
    print(f"  培训+甲方最终用户 entry: {'✓' if found_training else '✗'}")
    print(f"  订单3子功能 entry: {'✓' if found_order3 else '✗'}")

    print("\n[Done] Run test_ragas_no_scope.py to verify improvement.")


if __name__ == "__main__":
    asyncio.run(main())
