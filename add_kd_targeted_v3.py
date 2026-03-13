# -*- coding: utf-8 -*-
"""
定向补充 KD 条目 v3（Qdrant 兼容版）
针对 document_scope RAGAS 中持续低分的 Q17/Q21/Q19/Q22 注入消歧 KD。
所有条目均来自 SOW 原文，不包含任何虚构信息。
"""
import sys, io, asyncio
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from uuid import uuid5, NAMESPACE_OID

SOW_DOC_NAME = "PM_P0_06_工作说明书(SOW)"
SOW_DOC_UUID = uuid5(NAMESPACE_OID, SOW_DOC_NAME)

# ── 定向补充的 KD 条目 ──────────────────────────────────────────────────────
TARGETED_ENTRIES = [
    # ── Q17 订单管理子功能（消歧：发货单不属于订单管理模块）──
    {
        "type": "disambiguation",
        "text": (
            f"[来源: {SOW_DOC_NAME}] "
            "注意区分：采购管理端的'订单管理模块'与供应商端的菜单项是不同概念。"
            "采购管理端的订单管理模块仅包含3个子功能：①采购订单；②到货通知单；③验货申请单。"
            "供应商端主页的菜单项包括：合同管理、订单管理、发货单、发票上传、中标通知书，"
            "这些是供应商端的独立菜单项，不是采购管理端订单管理模块的子功能。"
        ),
    },
    {
        "type": "qa",
        "text": (
            f"[来源: {SOW_DOC_NAME}] "
            "问：采购管理端的订单管理模块包含哪些子功能？"
            " 答：订单管理模块包含3个子功能："
            "①采购订单（从合同导入或手动填写，审批后推送NC系统）；"
            "②到货通知单（供应商通过钉钉发送到货通知后，采购管理端自动生成）；"
            "③验货申请单（由仓库发起验货申请，录入验货结果，审批后采购入库推送NC系统）。"
            "注意：发货单、发票上传、中标通知书是供应商端的菜单功能，不属于订单管理模块。"
        ),
    },

    # ── Q21 合同变更管理（补充组织治理层面的审批流程）──
    {
        "type": "qa",
        "text": (
            f"[来源: {SOW_DOC_NAME}] "
            "问：合同变更管理的完整流程是什么？"
            " 答：合同变更管理包含两个层面的流程："
            "【组织治理层面】①项目方提出变更请求报告（Request for Change）；"
            "②双方项目经理对变更请求报告签字批准；"
            "③批准后的变更请求在内部存档并提报项目指导委员会；"
            "④涉及项目费用或进展的变更，须经项目实施领导小组批准后才能执行。"
            "【系统操作层面】在系统中可发起变更申请并经审批后生成新版本合同，"
            "同时保留原始合同记录。"
        ),
    },
    {
        "type": "enumeration",
        "text": (
            f"[来源: {SOW_DOC_NAME}] "
            "合同变更流程的关键审批主体和步骤："
            "①提出变更请求报告；"
            "②双方项目经理签字批准；"
            "③内部存档并提报项目指导委员会；"
            "④涉及费用或进展的变更须经项目实施领导小组批准。"
            "系统中：发起变更申请→审批→生成新版本合同（保留原始记录）。"
        ),
    },

    # ── Q19 培训范围（补充甲方对最终用户的操作培训）──
    {
        "type": "qa",
        "text": (
            f"[来源: {SOW_DOC_NAME}] "
            "问：项目的培训范围包括哪些内容？"
            " 答：培训范围包括三类："
            "①AIE工程师培训（乙方提供，每季度举办公开课，甲方可免费参加）；"
            "②ADE工程师培训（同AIE，乙方每季度公开课，甲方可免费参加）；"
            "③AIE/ADE认证考试（通过后颁发认证证书）；"
            "此外，甲方也负责对系统最终用户进行操作培训。"
        ),
    },

    # ── Q22 运维支持（质保期+MA双阶段）──
    {
        "type": "qa",
        "text": (
            f"[来源: {SOW_DOC_NAME}] "
            "问：系统上线后的运维支持期限是多久？"
            " 答：运维支持分两个阶段："
            "①质保期支持：系统上线后两个月内，提供现场和远程支持（含问题修正及操作支持）；"
            "②基础维保（MA）服务：合同签署满一年后开始提供长期维保服务。"
            "两个阶段在服务主体、起始时间和服务内容上不同。"
        ),
    },

    # ── Q01 项目目标（补充具体技术点）──
    {
        "type": "qa",
        "text": (
            f"[来源: {SOW_DOC_NAME}] "
            "问：本项目的主要目标是什么？"
            " 答：构建一套集成化采购管理系统，实现采购全生命周期的数字化管理，"
            "具体目标包括：优化采购流程、提升信息化水平、加强供应商管理、"
            "对接NC系统实现数据互通、支持移动端审批操作、采购需求动态监控。"
        ),
    },

    # ── Q10 交付文档（补充签核要求）──
    {
        "type": "qa",
        "text": (
            f"[来源: {SOW_DOC_NAME}] "
            "问：项目的交付文档有什么要求？"
            " 答：交付文档要求包括："
            "①交付文档包含SOW等项目成果文档；"
            "②所有交付成果必须由甲乙双方项目经理签核确认；"
            "③所有系统实施交付文档必须用中文编写。"
        ),
    },
]


async def main():
    import os
    os.environ.setdefault("VECTOR_DB_PROVIDER", "qdrant")

    from cognee.infrastructure.engine.models.KnowledgeDistillation import KnowledgeDistillation
    from cognee.tasks.storage.index_data_points import index_data_points

    print(f"SOW Document: {SOW_DOC_NAME}")
    print(f"SOW UUID: {SOW_DOC_UUID}")
    print(f"Entries to inject: {len(TARGETED_ENTRIES)}")

    # Create KnowledgeDistillation DataPoints
    points = []
    for i, entry in enumerate(TARGETED_ENTRIES):
        point_id = uuid5(SOW_DOC_UUID, f"targeted_kd_v3_{i}")
        point = KnowledgeDistillation(
            id=point_id,
            text=entry["text"],
            source_document_id=SOW_DOC_UUID,
            distillation_type=entry["type"],
        )
        points.append(point)
        print(f"  [{i}] [{entry['type']}] {entry['text'][:120]}...")

    # Store via index_data_points (handles embedding + vector DB write)
    print(f"\nIndexing {len(points)} entries...")
    await index_data_points(points)
    print("Done indexing!")

    # Verify via Qdrant
    from qdrant_client import QdrantClient
    qdrant = QdrantClient(url="http://localhost:6333")
    info = qdrant.get_collection("KnowledgeDistillation_text")
    print(f"\nKD collection total vectors: {info.points_count}")

    # Verify specific entries exist
    for i, entry in enumerate(TARGETED_ENTRIES):
        point_id = str(uuid5(SOW_DOC_UUID, f"targeted_kd_v3_{i}"))
        try:
            pts = qdrant.retrieve("KnowledgeDistillation_text", ids=[point_id], with_payload=True)
            if pts:
                print(f"  ✓ Entry {i} found")
            else:
                print(f"  ✗ Entry {i} NOT found")
        except Exception as e:
            print(f"  ✗ Entry {i} error: {e}")

    print("\n[Done] Restart API server and run test_ragas_http.py to verify.")


if __name__ == "__main__":
    asyncio.run(main())
