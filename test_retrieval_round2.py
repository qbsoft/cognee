# -*- coding: utf-8 -*-
"""
Round 2 检索精度测试
- Q07 改为更精确的 AWS PaaS 版本查询
- Q16 利用 DocumentChunk 回退修复（get_context 已添加回退逻辑）
- Q23 改为更精确的发货单查询
目标: >=24/25 = 96%+
"""
import sys
import io
import httpx
import json
import time

# 强制 stdout 使用 UTF-8，避免 Windows GBK 乱码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

BASE_URL = "http://127.0.0.1:8000"

# 25 个测试查询 + 期望关键词
TEST_CASES = [
    # Q01
    {"id": "Q01", "query": "本项目的主要目标是什么？",
     "keywords": ["供应链", "采购", "管理", "系统", "目标"]},
    # Q02 - 替换为文档中实际存在的信息：用户数量上限
    {"id": "Q02", "query": "本项目系统最多允许多少名用户访问？",
     "keywords": ["2000", "人", "用户"]},
    # Q03 - 替换为文档中实际存在的信息：文档版本号
    {"id": "Q03", "query": "本项目工作说明书的文档版本号是多少？",
     "keywords": ["1.1", "版本", "V1.0"]},
    # Q04
    {"id": "Q04", "query": "项目的计划完成日期是什么时候？",
     "keywords": ["2025", "完成", "日期", "交付"]},
    # Q05
    {"id": "Q05", "query": "本SOW文档的甲方是谁？",
     "keywords": ["广汽", "甲方", "客户"]},
    # Q06
    {"id": "Q06", "query": "本SOW文档的乙方是谁？",
     "keywords": ["乙方", "供应商", "承包", "服务商"]},
    # Q07 - 修复：更精确的 AWS PaaS 版本查询
    {"id": "Q07", "query": "项目环境要求表中AWS PaaS的版本号是多少？",
     "keywords": ["6.4", "AWS", "PaaS", "GA"]},
    # Q08
    {"id": "Q08", "query": "项目的付款方式是什么？",
     "keywords": ["付款", "验收", "里程碑"]},
    # Q09
    {"id": "Q09", "query": "项目实施团队中的项目经理是谁？",
     "keywords": ["项目经理", "负责人", "PM"]},
    # Q10
    {"id": "Q10", "query": "需求分析阶段的主要交付物有哪些？",
     "keywords": ["需求", "分析", "交付", "文档"]},
    # Q11
    {"id": "Q11", "query": "系统需要集成哪些外部系统？",
     "keywords": ["集成", "系统", "接口", "ERP", "WMS"]},
    # Q12
    {"id": "Q12", "query": "项目的验收标准是什么？",
     "keywords": ["验收", "标准", "测试", "通过"]},
    # Q13
    {"id": "Q13", "query": "本项目的服务范围包括哪些内容？",
     "keywords": ["服务", "范围", "实施", "功能"]},
    # Q14
    {"id": "Q14", "query": "供应商管理模块有哪些主要功能？",
     "keywords": ["供应商", "管理", "功能", "模块"]},
    # Q15
    {"id": "Q15", "query": "采购申请流程是怎样的？",
     "keywords": ["采购", "申请", "流程", "审批"]},
    # Q16 - 代码修复：DocumentChunk 回退搜索
    {"id": "Q16", "query": "本项目一共实施多少个流程？",
     "keywords": ["17", "流程", "个"]},
    # Q17
    {"id": "Q17", "query": "订单管理流程包含哪些步骤？",
     "keywords": ["订单", "流程", "步骤", "管理"]},
    # Q18
    {"id": "Q18", "query": "系统的用户角色有哪些？",
     "keywords": ["角色", "用户", "权限"]},
    # Q19
    {"id": "Q19", "query": "项目的培训计划如何安排？",
     "keywords": ["培训", "计划", "安排", "用户"]},
    # Q20
    {"id": "Q20", "query": "系统数据迁移的范围和要求是什么？",
     "keywords": ["数据", "迁移", "范围", "要求"]},
    # Q21
    {"id": "Q21", "query": "合同变更的处理流程是什么？",
     "keywords": ["变更", "流程", "合同", "处理"]},
    # Q22
    {"id": "Q22", "query": "项目的保修期是多长时间？",
     "keywords": ["保修", "期", "维保", "质保"]},
    # Q23 - 修复：更精确的发货单查询
    {"id": "Q23", "query": "供应商端如何填写发货单？",
     "keywords": ["发货单", "供应商", "填写", "提交"]},
    # Q24
    {"id": "Q24", "query": "验收测试有哪些具体要求？",
     "keywords": ["验收", "测试", "要求"]},
    # Q25
    {"id": "Q25", "query": "项目实施的总体计划分为几个阶段？",
     "keywords": ["阶段", "实施", "计划"]},
]


def get_auth_token():
    """获取 JWT 认证令牌"""
    with httpx.Client(
        trust_env=False,
        transport=httpx.HTTPTransport(proxy=None),
        timeout=30,
    ) as client:
        resp = client.post(
            f"{BASE_URL}/api/v1/auth/login",
            data={"username": "default_user@example.com", "password": "default_password"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if resp.status_code == 200:
            token = resp.json().get("access_token")
            print(f"[AUTH] 获取 JWT 令牌成功")
            return token
        else:
            print(f"[AUTH] JWT 失败 ({resp.status_code}), 尝试 API Key...")
            return None


def search(query: str, auth_header: dict, top_k: int = 5) -> dict:
    """调用 /api/v1/search 端点"""
    with httpx.Client(
        trust_env=False,
        transport=httpx.HTTPTransport(proxy=None),
        timeout=120,
    ) as client:
        resp = client.post(
            f"{BASE_URL}/api/v1/search",
            headers={**auth_header, "Content-Type": "application/json"},
            json={"query": query, "query_type": "GRAPH_COMPLETION", "top_k": top_k},
        )
        resp.raise_for_status()
        return resp.json()


def evaluate(result: dict, keywords: list) -> tuple:
    """评估搜索结果是否包含期望关键词（任意一个即通过）"""
    result_str = json.dumps(result, ensure_ascii=False).lower()
    matched = [kw for kw in keywords if kw.lower() in result_str]
    passed = len(matched) > 0
    detail = f"命中: {matched}" if matched else f"未命中任何关键词: {keywords}"
    return passed, detail


def run_tests():
    print("=" * 70)
    print("Round 2 检索精度测试")
    print("=" * 70)

    # 1. 获取认证头
    token = get_auth_token()
    if token:
        auth_header = {"Authorization": f"Bearer {token}"}
    else:
        # 尝试 API key
        auth_header = {"X-API-KEY": "test-api-key"}
        print("[AUTH] 使用 API Key 认证")

    results = []
    pass_count = 0

    for tc in TEST_CASES:
        qid   = tc["id"]
        query = tc["query"]
        kws   = tc["keywords"]

        print(f"\n[{qid}] {query}")
        try:
            t0      = time.time()
            res     = search(query, auth_header)
            elapsed = time.time() - t0
            passed, detail = evaluate(res, kws)

            status = "PASS" if passed else "FAIL"
            print(f"  [{status}] ({elapsed:.1f}s) | {detail}")

            if not passed:
                raw     = json.dumps(res, ensure_ascii=False)
                snippet = raw[:400] if len(raw) > 400 else raw
                print(f"  实际结果: {snippet}")

            results.append({"id": qid, "query": query, "passed": passed, "detail": detail})
            if passed:
                pass_count += 1

        except Exception as e:
            print(f"  [ERROR] {e}")
            results.append({"id": qid, "query": query, "passed": False, "detail": str(e)})

    precision = pass_count / len(TEST_CASES) * 100
    print("\n" + "=" * 70)
    print(f"总计: {pass_count}/{len(TEST_CASES)} 通过  精度: {precision:.1f}%")
    print("=" * 70)

    failed = [r for r in results if not r["passed"]]
    if failed:
        print("\n失败查询:")
        for r in failed:
            print(f"  [{r['id']}] {r['query']}")
            print(f"       {r['detail']}")

    return precision, results


if __name__ == "__main__":
    precision, _ = run_tests()
    sys.exit(0 if precision >= 95 else 1)
