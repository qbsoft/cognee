# -*- coding: utf-8 -*-
"""
Re-distill ONLY the SOW document chunks with proper doc_name.

Key fixes vs redistill_target.py:
1. Only processes SOW chunks (rows 300-345) — excludes 50 noise docs + technical manual
2. SimpleChunk has is_part_of.name = "PM_P0_06_工作说明书(SOW)"
   so [来源: PM_P0_06_工作说明书(SOW)] prefix is added to every KD entry
3. This enables document_scope="PM_P0_06_工作说明书(SOW)" filtering to work
4. No noise doc pollution in KD -> no-scope search also returns correct SOW answers

SOW chunk range: rows 300-345 in DocumentChunk_text table (46 chunks, ~34500 chars)
"""
import sys, io, asyncio, shutil, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from pathlib import Path

TARGET_DB_PATH = Path(
    "cognee/.cognee_system/databases/"
    "4817f5fd-55e1-4b68-a5bb-db705e415af4/"
    "4f7e8565-0463-5948-85a1-5511f1c971e9.lance.db"
)

# SOW document chunk range (verified by content analysis)
# [300-345]: SOW functional spec, implementation plan, acceptance criteria, sign-off
# [296-299]: Technical manual (山东尚能) — excluded
# [0-295]: Noise vendor proposals and contracts — excluded
SOW_CHUNK_START = 300
SOW_CHUNK_END = 345  # inclusive

# The exact document_scope value used in test_ragas_http.py
SOW_DOC_NAME = "PM_P0_06_工作说明书(SOW)"


async def main():
    import lancedb
    import cognee  # noqa: ensure logging/config setup

    from cognee.tasks.distillation.distill_knowledge import distill_knowledge
    from cognee.infrastructure.config.yaml_config import load_yaml_config
    from cognee.context_global_variables import vector_db_config
    from uuid import UUID, uuid5, NAMESPACE_OID

    print(f"Target DB: {TARGET_DB_PATH}")
    print(f"SOW document name: {SOW_DOC_NAME}")
    print(f"Chunk range: [{SOW_CHUNK_START}, {SOW_CHUNK_END}]")

    # ── Step 1: Delete ALL KD and DocumentIndexCard vectors ────────────────
    print("\nStep 1: Deleting existing KD and DocumentIndexCard vectors...")

    # Set context to target DB before deletion
    vector_db_config.set({
        "vector_db_url": str(TARGET_DB_PATH),
        "vector_db_key": "",
        "vector_db_provider": "lancedb",
    })

    for collection_name in ["KnowledgeDistillation_text", "DocumentIndexCard_summary"]:
        collection_path = TARGET_DB_PATH / f"{collection_name}.lance"
        if collection_path.exists():
            print(f"  Deleting: {collection_path}")
            shutil.rmtree(collection_path, ignore_errors=True)
        else:
            print(f"  Not found (OK): {collection_path}")

    print("  Done.")

    # ── Step 2: Load SOW chunks from LanceDB ────────────────────────────────
    print(f"\nStep 2: Loading SOW chunks (rows {SOW_CHUNK_START}-{SOW_CHUNK_END})...")
    db = await lancedb.connect_async(str(TARGET_DB_PATH))
    table = await db.open_table("DocumentChunk_text")
    df = await table.query().limit(400).to_pandas()

    print(f"  Total rows in DB: {len(df)}")

    # SOW document UUID (deterministic from doc name)
    sow_doc_uuid = uuid5(NAMESPACE_OID, SOW_DOC_NAME)
    print(f"  SOW document UUID: {sow_doc_uuid}")

    # Build SimpleChunk objects WITH proper doc_name
    class SimpleChunk:
        def __init__(self, chunk_id, text, doc_id, doc_name, chunk_index):
            self.id = chunk_id
            self.text = text
            self.chunk_index = chunk_index
            # is_part_of MUST have both 'id' and 'name' attributes
            # so _get_document_name() can extract the name for [来源:] prefix
            self.is_part_of = type('Doc', (), {
                'id': doc_id,
                'name': doc_name
            })()

    chunks = []
    for idx in range(SOW_CHUNK_START, min(SOW_CHUNK_END + 1, len(df))):
        row = df.iloc[idx]
        payload = row.get("payload", {})
        if isinstance(payload, dict):
            text_content = payload.get("text", "")
        else:
            text_content = row.get("text", "")

        if not text_content or len(text_content.strip()) < 10:
            continue

        chunk_id_str = row.get("id", "")
        if isinstance(payload, dict) and "id" in payload:
            chunk_id_str = payload["id"]

        try:
            chunk_id = UUID(chunk_id_str) if chunk_id_str else uuid5(NAMESPACE_OID, text_content[:100])
        except (ValueError, TypeError):
            chunk_id = uuid5(NAMESPACE_OID, text_content[:100])

        chunk = SimpleChunk(
            chunk_id=chunk_id,
            text=text_content,
            doc_id=sow_doc_uuid,
            doc_name=SOW_DOC_NAME,
            chunk_index=idx - SOW_CHUNK_START,  # relative index for ordering
        )
        chunks.append(chunk)

    total_chars = sum(len(c.text) for c in chunks)
    print(f"  Loaded {len(chunks)} SOW chunks ({total_chars:,} chars)")

    if not chunks:
        print("  ERROR: No SOW chunks found!")
        return

    # ── Step 3: Set context var and run distillation ─────────────────────────
    print(f"\nStep 3: Running distillation on {len(chunks)} SOW chunks...")

    vector_db_config.set({
        "vector_db_url": str(TARGET_DB_PATH),
        "vector_db_key": "",
        "vector_db_provider": "lancedb",
    })
    print(f"  ContextVar set: {TARGET_DB_PATH}")

    config = load_yaml_config("config/distillation.yaml")
    distillation_config = config.get("distillation", {})
    context_char_limit = distillation_config.get("context_char_limit", 50000)
    print(f"  Context char limit: {context_char_limit}")
    print(f"  Total chars: {total_chars} — {'single pass' if total_chars <= context_char_limit else 'hierarchical'}")

    t0 = time.time()
    await distill_knowledge(chunks, context_char_limit=context_char_limit)
    elapsed = time.time() - t0
    print(f"  Distillation completed in {elapsed:.1f}s")

    # ── Step 4: Verify KD vectors ────────────────────────────────────────────
    print("\nStep 4: Verifying KD vectors...")
    db2 = await lancedb.connect_async(str(TARGET_DB_PATH))
    tables = await db2.table_names()
    print(f"  Tables: {tables}")

    if "KnowledgeDistillation_text" in tables:
        kd_table = await db2.open_table("KnowledgeDistillation_text")
        count = await kd_table.count_rows()
        print(f"  KD vectors: {count}")

        sample_df = await kd_table.query().limit(count).to_pandas()
        has_prefix = 0
        has_17_flows = False
        for _, row in sample_df.iterrows():
            p = row.get("payload", {})
            text = p.get("text", "") if isinstance(p, dict) else ""
            if f"[来源: {SOW_DOC_NAME}]" in text:
                has_prefix += 1
            if "17" in text and "流程" in text:
                has_17_flows = True

        print(f"  Entries with [来源: {SOW_DOC_NAME}]: {has_prefix}/{count}")
        print(f"  Has '17个流程' entry: {has_17_flows}")

        # Show sample
        print("\n  Sample KD entries:")
        for i, (_, row) in enumerate(sample_df.iterrows()):
            if i >= 10:
                break
            p = row.get("payload", {})
            text = p.get("text", "") if isinstance(p, dict) else ""
            print(f"    [{i}] {text[:120]}")
    else:
        print("  ERROR: KnowledgeDistillation_text table not found!")

    if "DocumentIndexCard_summary" in tables:
        card_table = await db2.open_table("DocumentIndexCard_summary")
        card_count = await card_table.count_rows()
        print(f"\n  DocumentIndexCard vectors: {card_count}")
        card_df = await card_table.query().limit(5).to_pandas()
        for _, row in card_df.iterrows():
            p = row.get("payload", {})
            text = p.get("summary", p.get("text", "")) if isinstance(p, dict) else ""
            print(f"    Card: {str(text)[:150]}")
    else:
        print("  DocumentIndexCard_summary: not found")

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
