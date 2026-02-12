"""
LLM 增强分块器。

在语义分块基础上，使用 LLM 优化分块边界。
当 LLM 不可用时 graceful degradation 到原始分块。
"""
import logging
from typing import List, Dict, Any, Optional, Callable

logger = logging.getLogger(__name__)


class LLMEnhancedChunker:
    def __init__(self, llm_client: Optional[Callable] = None, max_chunk_size: int = 1500):
        self._llm_client = llm_client
        self.max_chunk_size = max_chunk_size

    async def refine(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not chunks or len(chunks) <= 1:
            return chunks
        try:
            suggestions = await self._get_llm_suggestions(chunks)
            if suggestions is None:
                return chunks
            result = self._apply_merges(chunks, suggestions.get("merge", []))
            for i, chunk in enumerate(result):
                chunk["chunk_index"] = i
            return result
        except Exception as e:
            logger.warning(f"LLM enhanced chunking failed, returning original chunks: {e}")
            return chunks

    async def _get_llm_suggestions(self, chunks: List[Dict[str, Any]]) -> Optional[Dict]:
        if self._llm_client is None:
            return None
        chunk_summaries = []
        for i, chunk in enumerate(chunks):
            preview = chunk["text"][:100] + ("..." if len(chunk["text"]) > 100 else "")
            chunk_summaries.append(f"[{i}] ({chunk['cut_type']}) {preview}")
        prompt_text = "\n".join(chunk_summaries)
        try:
            result = await self._llm_client(prompt_text)
            return result if isinstance(result, dict) else None
        except Exception:
            return None

    def _apply_merges(self, chunks: List[Dict[str, Any]], merge_groups: List[List[int]]) -> List[Dict[str, Any]]:
        if not merge_groups:
            return chunks
        merged_indices = set()
        result = []
        for group in merge_groups:
            for idx in group:
                merged_indices.add(idx)
        i = 0
        while i < len(chunks):
            in_group = None
            for group in merge_groups:
                if group and group[0] == i:
                    in_group = group
                    break
            if in_group:
                merged_text = "\n\n".join(chunks[idx]["text"] for idx in in_group if idx < len(chunks))
                result.append({"text": merged_text, "cut_type": "merged", "chunk_index": len(result)})
                i = max(in_group) + 1
            elif i not in merged_indices:
                result.append(chunks[i].copy())
                i += 1
            else:
                i += 1
        return result
