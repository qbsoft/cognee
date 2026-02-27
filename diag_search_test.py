"""
检索管道诊断测试脚本
运行方式: python diag_search_test.py
"""
import asyncio

async def main():
    import cognee
    from cognee.modules.search.types import SearchType

    queries = [
        "询比价管理功能描述是什么",
        "需求申请台账",
        "项目例会在什么时候",
    ]

    for q in queries:
        print(f"\n\n{'#'*70}")
        print(f"# 测试查询: {q}")
        print(f"{'#'*70}")

        result = await cognee.search(q, query_type=SearchType.GRAPH_COMPLETION)

        print(f"\n[最终结果] {result}")
        print(f"{'#'*70}\n")

if __name__ == "__main__":
    asyncio.run(main())
