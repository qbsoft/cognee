"""
图谱提取结果的多轮验证。

对 LLM 提取的实体-关系三元组进行第二轮验证：
- 使用 LLM 评估每条关系的准确性
- 为每条关系分配置信度评分 (0.0 ~ 1.0)
- 过滤低于置信度阈值的关系
- LLM 不可用时 graceful degradation（默认置信度 0.5）
"""
import logging
from typing import List, Dict, Any, Optional, Callable

logger = logging.getLogger(__name__)

DEFAULT_CONFIDENCE = 0.5


async def validate_extracted_graph(
    extracted_data: List[Dict[str, Any]],
    llm_client: Optional[Callable] = None,
    confidence_threshold: float = 0.7,
) -> List[Dict[str, Any]]:
    if not extracted_data:
        return []
    llm_failed = False
    try:
        if llm_client is None:
            raise ValueError("No LLM client provided")
        validation_input = _build_validation_input(extracted_data)
        validation_result = await llm_client(validation_input)
        scored_data = _apply_validation_scores(extracted_data, validation_result)
    except Exception as e:
        logger.warning(f"图谱验证失败 ({e})，使用默认置信度 {DEFAULT_CONFIDENCE}")
        scored_data = _apply_default_scores(extracted_data)
        llm_failed = True

    if llm_failed:
        logger.info(
            f"图谱验证: LLM 不可用，保留全部 {len(scored_data)} 条数据 (默认置信度: {DEFAULT_CONFIDENCE})"
        )
        return scored_data

    filtered = [
        item
        for item in scored_data
        if item.get("confidence", DEFAULT_CONFIDENCE) >= confidence_threshold
    ]
    logger.info(
        f"图谱验证: {len(extracted_data)} 条输入 → {len(filtered)} 条通过 (阈值: {confidence_threshold})"
    )
    return filtered


def _build_validation_input(extracted_data: List[Dict[str, Any]]) -> str:
    lines = []
    for i, item in enumerate(extracted_data):
        source = item.get("source_entity", "?")
        target = item.get("target_entity", "?")
        rel = item.get("relationship", "?")
        text = item.get("source_text", "")[:200]
        lines.append(f"[{i}] {source} --{rel}--> {target} (source: {text})")
    return "\n".join(lines)


def _apply_validation_scores(
    extracted_data: List[Dict[str, Any]],
    validation_result: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    score_map = {}
    for item in validation_result:
        idx = item.get("index")
        if idx is not None:
            score_map[idx] = item
    result = []
    for i, data in enumerate(extracted_data):
        scored_item = data.copy()
        if i in score_map:
            scored_item["confidence"] = score_map[i].get("confidence", DEFAULT_CONFIDENCE)
            scored_item["validation_reason"] = score_map[i].get("reason", "")
        else:
            scored_item["confidence"] = DEFAULT_CONFIDENCE
        result.append(scored_item)
    return result


def _apply_default_scores(
    extracted_data: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    result = []
    for data in extracted_data:
        item = data.copy()
        item["confidence"] = DEFAULT_CONFIDENCE
        result.append(item)
    return result
