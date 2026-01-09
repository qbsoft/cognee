def translate_relationship_name(relationship_name: str) -> str:
    """
    翻译系统内置的英文关系名称为中文。
    如果关系名称已经是中文，则直接返回。
    
    Args:
        relationship_name: 关系名称（可能是英文或中文）
    
    Returns:
        翻译后的关系名称（中文）或原名称（如果已经是中文）
    """
    # 系统内置的英文关系名称翻译映射
    translations = {
        "is_part_of": "部分属于",
        "contains": "包含",
        "is_a": "是",
        "exists_in": "存在于",
        "mentioned_in": "提及于",
        "made_from": "由...制成",
        "has": "有",
        "belongs_to": "属于",
        "belongs_to_set": "属于集合",
        "relates_to": "关联到",
        "part_of": "部分属于",
        "derived_from": "派生自",
        "references": "引用",
        "mentions": "提及",
        "describes": "描述",
        "uses": "使用",
        "implements": "实现",
        "extends": "扩展",
        "calls": "调用",
        "depends_on": "依赖于",
    }
    
    # 转换为小写进行匹配
    lower_name = relationship_name.lower()
    
    # 如果存在翻译，返回中文翻译
    if lower_name in translations:
        return translations[lower_name]
    
    # 如果已经是中文（包含中文字符），直接返回
    if any('\u4e00' <= char <= '\u9fff' for char in relationship_name):
        return relationship_name
    
    # 否则返回原名称（可能是其他语言的英文关系名称）
    return relationship_name

