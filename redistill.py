# -*- coding: utf-8 -*-
"""
Re-run only the knowledge distillation step without full cognify.
Deletes old KD vectors and generates new ones from existing document chunks.
Sets the correct database ContextVar so vectors go to the right database.
"""
import sys, io, asyncio, shutil, glob, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from pathlib import Path

DB_ROOT = Path("cognee/.cognee_system/databases")


async def main():
    import lancedb
    import cognee  # noqa: ensure logging/config setup

    from cognee.tasks.distillation.distill_knowledge import distill_knowledge
    from cognee.infrastructure.config.yaml_config import load_yaml_config
    from cognee.context_global_variables import vector_db_config
    from cognee.modules.users.methods import get_default_user
    from uuid import UUID, uuid5, NAMESPACE_OID

    # Auto-detect user ID from cognee's default user
    user = await get_default_user()
    USER_ID = str(user.id)
    print(f"Detected default user: {USER_ID}")

    # Minimal chunk wrapper
    class SimpleChunk:
        def __init__(self, chunk_id, text, doc_id=None):
            self.id = chunk_id
            self.text = text
            self.chunk_index = 0
            if doc_id:
                self.is_part_of = type('Doc', (), {'id': doc_id})()
            else:
                self.is_part_of = None

    user_db_root = DB_ROOT / USER_ID

    # Step 1: Delete old KD vector collections for this user
    print("Step 1: Deleting old KD vector collections...")
    kd_dirs = glob.glob(str(user_db_root / "**" / "KnowledgeDistillation_text.lance"), recursive=True)
    for kd_dir in kd_dirs:
        print(f"  Deleting: {kd_dir}")
        shutil.rmtree(kd_dir, ignore_errors=True)
    # Also delete from default cognee.lancedb
    default_kd = DB_ROOT / "cognee.lancedb" / "KnowledgeDistillation_text.lance"
    if default_kd.exists():
        print(f"  Deleting (default): {default_kd}")
        shutil.rmtree(default_kd, ignore_errors=True)
    kd_dirs_all = glob.glob(str(DB_ROOT / "**" / "KnowledgeDistillation_text.lance"), recursive=True)
    for kd_dir in kd_dirs_all:
        print(f"  Deleting: {kd_dir}")
        shutil.rmtree(kd_dir, ignore_errors=True)
    print("  All KD collections deleted")

    # Step 2: Find and process document chunks across ALL user databases
    # (data may be stored under a different user ID than the current default user)
    print(f"\nStep 2: Finding document chunks across all databases (current user: {USER_ID})...")
    lance_dbs = list(DB_ROOT.rglob("DocumentChunk_text.lance"))
    print(f"  Found {len(lance_dbs)} database(s) with DocumentChunk_text")

    for chunk_path in lance_dbs:
        db_path = chunk_path.parent
        dataset_id = db_path.stem.replace(".lance", "")
        print(f"\n  === Processing dataset: {dataset_id} ===")
        print(f"  Database: {db_path}")

        # SET THE CONTEXT VAR to point vector engine to the right database
        vector_db_config.set({
            "vector_db_url": str(db_path),
            "vector_db_key": "",
            "vector_db_provider": "lancedb",
        })
        print(f"  ContextVar set: vector_db_url = {db_path}")

        db = await lancedb.connect_async(str(db_path))
        table = await db.open_table("DocumentChunk_text")
        df = await table.query().limit(2000).to_pandas()
        print(f"  Found {len(df)} chunks")

        if len(df) == 0:
            continue

        # Build SimpleChunk objects
        chunks = []
        for _, row in df.iterrows():
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

            doc_uuid = UUID(dataset_id) if dataset_id else chunk_id
            chunk = SimpleChunk(chunk_id=chunk_id, text=text_content, doc_id=doc_uuid)
            chunks.append(chunk)

        total_chars = sum(len(c.text) for c in chunks)
        print(f"  Reconstructed {len(chunks)} chunks ({total_chars} chars)")

        if not chunks:
            continue

        # Read config
        config = load_yaml_config("config/distillation.yaml")
        distillation_config = config.get("distillation", {})
        context_char_limit = distillation_config.get("context_char_limit", 50000)

        # Run distillation
        print(f"  Running distillation (limit={context_char_limit})...")
        t0 = time.time()
        await distill_knowledge(chunks, context_char_limit=context_char_limit)
        elapsed = time.time() - t0
        print(f"  Distillation completed in {elapsed:.1f}s")

    # Step 3: Verify new KD vectors
    print("\n\nStep 3: Verifying new KD vectors...")
    new_kd_dirs = glob.glob(str(user_db_root / "**" / "KnowledgeDistillation_text.lance"), recursive=True)
    if not new_kd_dirs:
        print("  WARNING: No KD vectors found in user database!")
        # Check default location
        default_check = glob.glob(str(DB_ROOT / "**" / "KnowledgeDistillation_text.lance"), recursive=True)
        for kd_dir in default_check:
            print(f"  Found in other location: {kd_dir}")

    for kd_dir in new_kd_dirs:
        db = await lancedb.connect_async(str(Path(kd_dir).parent))
        table = await db.open_table("KnowledgeDistillation_text")
        count = await table.count_rows()
        print(f"  {kd_dir}: {count} vectors")

        sample = await table.query().limit(5).to_pandas()
        for _, row in sample.iterrows():
            payload = row.get("payload", {})
            if isinstance(payload, dict):
                text = payload.get("text", "")[:120]
                dtype = payload.get("distillation_type", "?")
            else:
                text = str(row.get("text", ""))[:120]
                dtype = row.get("distillation_type", "?")
            print(f"    [{dtype}] {text}")

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
