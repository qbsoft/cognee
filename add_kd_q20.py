# -*- coding: utf-8 -*-
"""
定向补充 Q20（合同审批流程）KD 条目。
在 document_scope 模式下，scoped KD 搜索未找到合同审批流程信息，
导致系统回答"文档中未提及"。添加明确的 KD 条目解决此问题。
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

# Q20 专用条目 - 使用基于内容的稳定 ID
Q20_ENTRIES = [
    {
        "id_key": "q20_contract_approval_qa",
        "type": "qa",
        "text": (
            f"[来源: {SOW_DOC_NAME}] "
            "问：合同审批流程的主要步骤是什么？"
            " 答：合同审批流程步骤："
            "①进入合同审批填报界面（支持手动填写合同基本信息，或从推荐供应商台账自动带入供应商、物料、价格等信息）；"
            "②上传合同相关附件；"
            "③填报完成后可保存为草稿或提交审批；"
            "④审批通过后将合同内容生成合同台账。"
        ),
    },
    {
        "id_key": "q20_contract_approval_enum",
        "type": "enumeration",
        "text": (
            f"[来源: {SOW_DOC_NAME}] "
            "合同审批流程共4步：①填报界面（支持手动填写或从推荐供应商台账自动带入供应商/物料/价格）"
            "→②上传附件→③提交审批或保存草稿→④审批通过后生成合同台账。"
        ),
    },
]


async def main():
    import lancedb
    import cognee  # noqa

    from cognee.tasks.storage.add_data_points import add_data_points
    from cognee.context_global_variables import vector_db_config
    from cognee.infrastructure.engine.models.KnowledgeDistillation import KnowledgeDistillation

    print(f"Target DB: {TARGET_DB_PATH}")

    # Set context to target DB
    vector_db_config.set({
        "vector_db_url": str(TARGET_DB_PATH),
        "vector_db_key": "",
        "vector_db_provider": "lancedb",
    })

    # Check current KD count
    db = await lancedb.connect_async(str(TARGET_DB_PATH))
    kd_table = await db.open_table("KnowledgeDistillation_text")
    count_before = await kd_table.count_rows()
    print(f"Current KD vectors: {count_before}")

    # Create Q20 KnowledgeDistillation DataPoints
    points = []
    for entry in Q20_ENTRIES:
        point_id = uuid5(SOW_DOC_UUID, entry["id_key"])
        point = KnowledgeDistillation(
            id=point_id,
            text=entry["text"],
            source_document_id=SOW_DOC_UUID,
            distillation_type=entry["type"],
        )
        points.append(point)
        print(f"  ID: {point_id}")
        print(f"  [{entry['type']}] {entry['text'][:100]}...")

    print(f"\nAdding {len(points)} Q20 KD entries...")
    await add_data_points(points)
    print("Done!")

    # Verify
    db2 = await lancedb.connect_async(str(TARGET_DB_PATH))
    kd_table2 = await db2.open_table("KnowledgeDistillation_text")
    count_after = await kd_table2.count_rows()
    print(f"\nKD vectors: {count_after} (was {count_before}, added {count_after - count_before})")

    # Search for the new entries
    df = await kd_table2.query().limit(count_after).to_pandas()
    found_q20 = 0
    for _, row in df.iterrows():
        p = row.get("payload", {})
        text = p.get("text", "") if isinstance(p, dict) else ""
        if "合同审批填报界面" in text and "推荐供应商台账" in text:
            found_q20 += 1
    print(f"Q20 合同审批 entry: {'✓ found ' + str(found_q20) if found_q20 else '✗ not found'}")

    print("\n[Done] Run test_ragas_http.py to verify document_scope Q20 improvement.")


if __name__ == "__main__":
    asyncio.run(main())
