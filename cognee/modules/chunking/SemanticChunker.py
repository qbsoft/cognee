"""
语义感知分块器。

利用 Markdown 文档结构（标题、表格、代码块）进行智能分块：
- 按标题层级分割
- 表格作为整体不拆散
- 代码块作为整体不分割
- 超长段落按句子边界分割
- 支持块间重叠
"""
import re
import logging
from typing import List, Dict, Any, Generator

logger = logging.getLogger(__name__)


class SemanticChunker:
    def __init__(self, max_chunk_size: int = 1500, overlap: int = 0):
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap

    def chunk(self, text: str) -> Generator[Dict[str, Any], None, None]:
        if not text or not text.strip():
            return
        segments = self._split_into_segments(text)
        merged = self._merge_and_split_segments(segments)
        chunk_index = 0
        prev_tail = ""
        for segment in merged:
            chunk_text = segment["text"]
            if self.overlap > 0 and prev_tail:
                chunk_text = prev_tail + "\n\n" + chunk_text
            yield {
                "text": chunk_text.strip(),
                "cut_type": segment["cut_type"],
                "chunk_index": chunk_index,
            }
            if self.overlap > 0:
                prev_tail = segment["text"][-self.overlap:]
            chunk_index += 1

    def _split_into_segments(self, text: str) -> List[Dict[str, Any]]:
        segments = []
        lines = text.split("\n")
        current_segment = []
        current_type = "paragraph"
        in_code_block = False
        in_table = False

        for line in lines:
            if line.strip().startswith("```"):
                if in_code_block:
                    current_segment.append(line)
                    segments.append({"text": "\n".join(current_segment), "cut_type": "code"})
                    current_segment = []
                    current_type = "paragraph"
                    in_code_block = False
                    continue
                else:
                    if current_segment:
                        seg_text = "\n".join(current_segment).strip()
                        if seg_text:
                            segments.append({"text": seg_text, "cut_type": current_type})
                    current_segment = [line]
                    current_type = "code"
                    in_code_block = True
                    continue

            if in_code_block:
                current_segment.append(line)
                continue

            is_table_line = bool(re.match(r"^\s*\|.*\|\s*$", line))
            if is_table_line:
                if not in_table:
                    if current_segment:
                        seg_text = "\n".join(current_segment).strip()
                        if seg_text:
                            segments.append({"text": seg_text, "cut_type": current_type})
                    current_segment = [line]
                    current_type = "table"
                    in_table = True
                else:
                    current_segment.append(line)
                continue
            elif in_table:
                segments.append({"text": "\n".join(current_segment), "cut_type": "table"})
                current_segment = []
                current_type = "paragraph"
                in_table = False

            if re.match(r"^#{1,6}\s+", line):
                if current_segment:
                    seg_text = "\n".join(current_segment).strip()
                    if seg_text:
                        segments.append({"text": seg_text, "cut_type": current_type})
                current_segment = [line]
                current_type = "heading"
                continue

            current_segment.append(line)

        if current_segment:
            seg_text = "\n".join(current_segment).strip()
            if seg_text:
                segments.append({"text": seg_text, "cut_type": current_type if not in_table else "table"})

        return segments

    def _merge_and_split_segments(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        result = []
        buffer_text = ""
        buffer_type = "paragraph"

        for seg in segments:
            seg_text = seg["text"]
            seg_type = seg["cut_type"]

            if seg_type in ("table", "code"):
                if buffer_text.strip():
                    for chunk in self._split_if_too_long(buffer_text.strip(), buffer_type):
                        result.append(chunk)
                    buffer_text = ""
                result.append({"text": seg_text, "cut_type": seg_type})
                continue

            if seg_type == "heading":
                if buffer_text.strip():
                    for chunk in self._split_if_too_long(buffer_text.strip(), buffer_type):
                        result.append(chunk)
                buffer_text = seg_text
                buffer_type = "heading"
                continue

            candidate = (buffer_text + "\n\n" + seg_text).strip() if buffer_text else seg_text
            if len(candidate) <= self.max_chunk_size:
                buffer_text = candidate
                if buffer_type == "paragraph":
                    buffer_type = seg_type
            else:
                if buffer_text.strip():
                    for chunk in self._split_if_too_long(buffer_text.strip(), buffer_type):
                        result.append(chunk)
                buffer_text = seg_text
                buffer_type = seg_type

        if buffer_text.strip():
            for chunk in self._split_if_too_long(buffer_text.strip(), buffer_type):
                result.append(chunk)

        return result

    def _split_if_too_long(self, text: str, cut_type: str) -> List[Dict[str, Any]]:
        if len(text) <= self.max_chunk_size:
            return [{"text": text, "cut_type": cut_type}]

        sentences = re.split(r"(?<=[.!?。！？\n])\s+", text)
        result = []
        current = ""

        for sentence in sentences:
            candidate = (current + " " + sentence).strip() if current else sentence
            if len(candidate) <= self.max_chunk_size:
                current = candidate
            else:
                if current:
                    result.append({"text": current.strip(), "cut_type": cut_type})
                if len(sentence) > self.max_chunk_size:
                    for i in range(0, len(sentence), self.max_chunk_size):
                        result.append({"text": sentence[i:i + self.max_chunk_size], "cut_type": "size_limit"})
                    current = ""
                else:
                    current = sentence

        if current.strip():
            result.append({"text": current.strip(), "cut_type": cut_type})

        return result
