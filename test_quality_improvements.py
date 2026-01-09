"""
数据质量改进功能快速测试脚本

使用方法：
1. 确保后端服务正在运行
2. 设置环境变量或修改脚本中的配置
3. 运行: python test_quality_improvements.py
"""
import asyncio
import sys
from uuid import UUID
from typing import Optional

# 添加项目路径
sys.path.insert(0, '.')

from cognee.infrastructure.databases.graph import get_graph_engine
from cognee.modules.graph.utils.entity_normalization import (
    normalize_entity_name,
    find_similar_entities,
    calculate_string_similarity,
)
from cognee.modules.graph.utils.entity_quality_scorer import (
    calculate_entity_quality_score,
)
from cognee.modules.graph.utils.relationship_validator import (
    validate_relationship,
)
from cognee.modules.graph.utils.data_integrity_checker import (
    check_node_integrity,
    generate_integrity_report,
)
from cognee.modules.graph.utils.quality_report import generate_quality_report
from cognee.modules.search.utils.quality_metrics import (
    calculate_search_quality_metrics,
)
from cognee.modules.retrieval.utils.result_quality_scorer import (
    calculate_result_relevance_score,
)
from cognee.modules.engine.models import Entity, EntityType


def test_entity_normalization():
    """测试实体名称规范化"""
    print("\n=== 测试1: 实体名称规范化 ===")
    
    test_cases = [
        ("  临时冻结  ", "临时冻结"),
        ("临时冻结。", "临时冻结"),
        ("TEMP", "temp"),
        ("临时冻结措施", "临时冻结措施"),
    ]
    
    all_passed = True
    for input_name, expected in test_cases:
        result = normalize_entity_name(input_name)
        passed = result == expected or result.lower() == expected.lower()
        status = "✅" if passed else "❌"
        print(f"{status} 输入: '{input_name}' -> 输出: '{result}' (期望: '{expected}')")
        if not passed:
            all_passed = False
    
    return all_passed


def test_string_similarity():
    """测试字符串相似度计算"""
    print("\n=== 测试2: 字符串相似度计算 ===")
    
    test_cases = [
        ("临时冻结", "临时冻结", 1.0),
        ("临时冻结", "临时冻结措施", 0.85),  # 应该高度相似
        ("临时冻结", "罚款", 0.0),  # 应该不相似
    ]
    
    all_passed = True
    for str1, str2, min_similarity in test_cases:
        similarity = calculate_string_similarity(str1, str2)
        passed = similarity >= min_similarity if min_similarity > 0.5 else similarity < 0.5
        status = "✅" if passed else "❌"
        print(f"{status} '{str1}' vs '{str2}': {similarity:.3f} (最小: {min_similarity})")
        if not passed:
            all_passed = False
    
    return all_passed


def test_entity_quality_score():
    """测试实体质量评分"""
    print("\n=== 测试3: 实体质量评分 ===")
    
    # 创建高质量实体
    high_quality_entity = Entity(
        id="test-1",
        name="董事长",
        description="董事会的负责人，由董事会全体董事过半数选举产生",
        is_a=EntityType(id="type-1", name="职位"),
        ontology_valid=True,
    )
    
    # 创建低质量实体
    low_quality_entity = Entity(
        id="test-2",
        name="",  # 空名称
        description="",  # 空描述
        is_a=EntityType(id="type-2", name="NodeSet"),  # 系统类型
        ontology_valid=False,
    )
    
    high_score = calculate_entity_quality_score(high_quality_entity)
    low_score = calculate_entity_quality_score(low_quality_entity)
    
    print(f"高质量实体分数: {high_score:.3f} (期望: ≥ 0.7)")
    print(f"低质量实体分数: {low_score:.3f} (期望: < 0.5)")
    
    passed = high_score >= 0.7 and low_score < 0.5
    status = "✅" if passed else "❌"
    print(f"{status} 质量评分测试")
    
    return passed


def test_relationship_validation():
    """测试关系合理性验证"""
    print("\n=== 测试4: 关系合理性验证 ===")
    
    test_cases = [
        # (源类型, 关系, 目标类型, 是否有效)
        ("DocumentChunk", "contains", "Entity", True),
        ("Entity", "is_a", "EntityType", True),
        ("DocumentChunk", "is_a", "DocumentChunk", False),  # 无效
        ("Entity", "belongs_to_set", "NodeSet", True),
    ]
    
    all_passed = True
    for source_type, relationship, target_type, expected_valid in test_cases:
        is_valid, error_msg = validate_relationship(
            source_type, relationship, target_type
        )
        passed = is_valid == expected_valid
        status = "✅" if passed else "❌"
        print(f"{status} {source_type} --[{relationship}]--> {target_type}: "
              f"{'有效' if is_valid else '无效'} (期望: {'有效' if expected_valid else '无效'})")
        if not passed:
            print(f"   错误信息: {error_msg}")
            all_passed = False
    
    return all_passed


async def test_data_integrity(dataset_id: Optional[UUID] = None):
    """测试数据完整性检查"""
    print("\n=== 测试5: 数据完整性检查 ===")
    
    try:
        # 创建测试节点
        from cognee.modules.graph.cognee_graph.CogneeGraphElements import Node
        
        nodes = [
            Node("node-1", {"name": "测试节点1", "type": "Entity"}),
            Node("node-2", {"name": "", "type": "Entity"}),  # 空名称
            Node("node-3", {"name": "测试节点3", "type": "Entity"}),  # 孤立节点
        ]
        
        edges = []  # 空边列表，node-3将是孤立节点
        
        issues = check_graph_integrity(nodes, edges)
        
        print(f"孤立节点数: {len(issues['orphan_nodes'])} (期望: ≥ 1)")
        print(f"空名称节点数: {len(issues['empty_names'])} (期望: ≥ 1)")
        
        passed = len(issues['orphan_nodes']) >= 1 and len(issues['empty_names']) >= 1
        status = "✅" if passed else "❌"
        print(f"{status} 完整性检查测试")
        
        return passed
    except Exception as e:
        print(f"❌ 完整性检查测试失败: {str(e)}")
        return False


def test_result_quality_scorer():
    """测试检索结果质量评分"""
    print("\n=== 测试6: 检索结果质量评分 ===")
    
    try:
        from cognee.modules.graph.cognee_graph.CogneeGraphElements import Node, Edge
        
        # 创建测试节点
        node1 = Node("node-1", {
            "name": "临时冻结",
            "description": "临时冻结不得超过四十八小时",
            "type": "Entity",
            "vector_distance": 0.1,  # 高相关性
        })
        
        node2 = Node("node-2", {
            "name": "无关节点",
            "description": "这是一个无关的节点",
            "type": "Entity",
            "vector_distance": 0.9,  # 低相关性
        })
        
        edge = Edge(node1, node2, {"relationship_name": "关联"})
        
        query = "临时冻结"
        score1 = calculate_result_relevance_score(query, node1, edge)
        score2 = calculate_result_relevance_score(query, node2, edge)
        
        print(f"相关节点质量分数: {score1:.3f} (期望: ≥ 0.7)")
        print(f"无关节点质量分数: {score2:.3f} (期望: < 0.5)")
        
        passed = score1 >= 0.7 and score2 < 0.5
        status = "✅" if passed else "❌"
        print(f"{status} 检索结果质量评分测试")
        
        return passed
    except Exception as e:
        print(f"❌ 检索结果质量评分测试失败: {str(e)}")
        return False


async def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("数据质量改进功能测试")
    print("=" * 60)
    
    results = []
    
    # 测试1: 实体名称规范化
    results.append(("实体名称规范化", test_entity_normalization()))
    
    # 测试2: 字符串相似度
    results.append(("字符串相似度计算", test_string_similarity()))
    
    # 测试3: 实体质量评分
    results.append(("实体质量评分", test_entity_quality_score()))
    
    # 测试4: 关系合理性验证
    results.append(("关系合理性验证", test_relationship_validation()))
    
    # 测试5: 数据完整性检查
    results.append(("数据完整性检查", await test_data_integrity()))
    
    # 测试6: 检索结果质量评分
    results.append(("检索结果质量评分", test_result_quality_scorer()))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed_count = 0
    total_count = len(results)
    
    for test_name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{status} - {test_name}")
        if passed:
            passed_count += 1
    
    print(f"\n总计: {passed_count}/{total_count} 测试通过")
    
    if passed_count == total_count:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print(f"\n⚠️  有 {total_count - passed_count} 个测试失败，请检查上述输出")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(run_all_tests())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n测试过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

