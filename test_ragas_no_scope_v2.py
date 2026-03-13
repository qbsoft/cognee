# -*- coding: utf-8 -*-
"""
通过 HTTP API 调用 cognee 后端的 RAGAS 评测脚本
场景: no_scope（自由搜索），不指定 document_scope
问题集: 混合场景 — 自然语言 / 领域术语 / 跨文档
"""
import sys, io, json, time, os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import httpx

# ==============================================================
# Configuration
# ==============================================================
COGNEE_API_BASE = os.getenv("COGNEE_API_BASE", "http://localhost:8000")
LLM_API_KEY = os.getenv("LLM_API_KEY", "sk-f9235546f8944cdca5529643bfa153f1")
LLM_ENDPOINT = os.getenv("LLM_ENDPOINT", "https://dashscope.aliyuncs.com/compatible-mode/v1")

# ==============================================================
# Ground Truth — 混合场景问题集
# 类型: N=自然语言  D=领域术语  X=跨文档/综合
# ==============================================================
GROUND_TRUTH = {
    # ── 自然语言（无实体名，纯内容匹配）──
    "Q01": "17个流程",  # N: 极简事实
    "Q02": "没有严重缺陷及甲方不可接受的中等缺陷；各方已同意并拟定处理遗留缺陷的期限及计划；系统上线验收以系统上线申请报告签批完成为标志；最终验收在系统上线运行3个月内完成",  # N
    "Q03": "两种形式：分项验收（需求设计验收、系统上线验收，按里程碑阶段进行）和最终验收（系统上线运行3个月内）",  # N
    "Q04": "供应商注册审核（准入审核、多级审批）、供应商档案管理（基本信息/联系方式/银行账户/资质证书）、供应商分类管理、供应商评价（物流时效/产品质量等维度打分）",  # N
    "Q05": "填写采购需求申请表单→系统查询库存（对接NC）→自动匹配流程分支→可选加急流程→支持平库操作→上传附件→流程完成后进入需求台账，后续可发起询比价或招标",  # N
    "Q06": "订单管理包含3个子功能：采购订单（从合同导入或手动填写、审批后推送NC）、到货通知单（供应商发货后仓库生成）、验货申请单（仓库发起验货申请、审批后采购入库推送NC）",  # N
    "Q07": "合同审批流程：填报界面（支持手动填写或从推荐供应商台账自动带入供应商、物料、价格等信息）→上传附件→提交审批或保存草稿→审批通过后生成合同台账",  # N
    "Q08": "在供应商平台→订单管理→查询采购方订单→关联订单发起发货单→填写发货物料信息、规格型号、数量等关键字段",  # N

    # ── 领域术语（含专业概念但无公司名）──
    "Q09": "AWS PaaS 6.4.GA（实例安装版，非集群）",  # D
    "Q10": "AWS PaaS控制台仅支持A级浏览器（IE10+、Chrome35+、Firefox30+）；AWS PaaS客户端同时支持A、B级浏览器（B级含IE8/9，不推荐）；IE必须运行在非兼容性模式；分辨率不低于1024×768",  # D
    "Q11": "AIE工程师培训、ADE工程师培训、AIE/ADE认证考试；乙方每季度举办公开课，免费参加，通过后颁发证书；甲方也负责对最终用户进行操作培训",  # D
    "Q12": "合同变更管理流程：提出变更请求报告→双方项目经理签字批准→内部存档并提报项目指导委员会；涉及费用或进展的变更须经项目实施领导小组批准；系统中可发起变更申请并经审批生成新版本合同",  # D
    "Q13": "系统上线后两个月内提供现场和远程支持（质保期支持），包含问题修正及操作支持；另有基础维保服务（MA）从合同签署满一年后开始",  # D
    "Q14": "用友NC6.5（ERP系统，涉及11类业务数据集成）和钉钉（移动审批平台）",  # D

    # ── 跨文档/综合（测试系统在52文档中找到正确文档的能力）──
    "Q15": "服务范围包括：采购管理端和供应商端的流程实施（17个流程）；AWS PaaS平台部署；与NC6.5和钉钉的系统集成（涉及11类业务数据）；AIE/ADE工程师培训及认证；上线后两个月支持保障；基础维保（MA）服务",  # X
    "Q16": "项目交付文档包括工作说明书（SOW）等；甲乙双方各自任命项目经理作为授权代表签核交付文档；所有系统实施交付文档用中文编写",  # X
    "Q17": "乙方职责：提供采购系统实施服务、培训甲方技术人员（AIE/ADE工程师培训）、执行项目交付；甲方职责：提供硬件环境和办公条件、配合接口开发联调、确保项目组专职人员有决策权、主导多厂商协同",  # X
    "Q18": "文档中描述的项目实施阶段划分为五个阶段：项目准备（目标定义）、蓝图设计（目标分解）、系统建设（目标实现）、上线验收（客户价值实现）、上线支持（投资收益最大化）",  # X
    "Q19": "V1.1",  # X: 简单但需找对文档
    "Q20": "最多2000名用户（访问用户不超过2000人，集团公司一级组织）",  # X

    # ── 否定题（系统应正确回答"未规定"）──
    "Q21": "文档中未明确给出项目计划完成日期",  # N
    "Q22": "SOW文档中未明确规定付款里程碑的具体划分方式、付款比例或付款时间节点",  # N

    # ── 关系题（甲乙方信息）──
    "Q23": "山东正和热电有限公司",  # X: 甲方
    "Q24": "山东佳航智能科技有限公司",  # X: 乙方
    "Q25": "优化采购流程，提升信息化管理水平，构建采购管理系统实现全流程管控；通过对接NC系统、支持移动端操作、加强供应商管理与采购需求动态监控，降低采购成本，提升采购效率",  # X
}

QUERIES = [
    # ── 自然语言（无实体，纯内容匹配）──
    ("Q01", "采购管理系统一共要实施多少个流程？"),
    ("Q02", "采购管理系统项目的验收标准是什么？"),
    ("Q03", "项目验收有哪几种形式？"),
    ("Q04", "供应商管理模块有哪些主要功能？"),
    ("Q05", "采购申请流程的步骤是怎样的？"),
    ("Q06", "订单管理模块包含哪些子功能？"),
    ("Q07", "合同审批流程的主要步骤是什么？"),
    ("Q08", "供应商端如何填写发货单？"),

    # ── 领域术语（含专业概念）──
    ("Q09", "AWS PaaS平台的版本号和部署方式是什么？"),
    ("Q10", "AWS PaaS对客户端浏览器有什么要求？"),
    ("Q11", "AIE和ADE工程师培训是怎么安排的？培训范围包括什么？"),
    ("Q12", "合同变更管理的审批流程和治理要求是什么？"),
    ("Q13", "系统上线后的质保期支持和MA维保服务分别是多久？"),
    ("Q14", "BPMS采购系统需要与哪些ERP和移动平台集成？"),

    # ── 跨文档/综合 ──
    ("Q15", "采购管理系统的服务范围包括哪些内容？"),
    ("Q16", "采购管理系统项目对交付文档有什么要求？"),
    ("Q17", "采购管理系统项目中甲方和乙方各自的主要职责是什么？"),
    ("Q18", "采购管理系统项目实施的总体计划分为几个阶段？"),
    ("Q19", "采购管理系统工作说明书的文档版本号是多少？"),
    ("Q20", "采购管理系统最多允许多少名用户访问？"),

    # ── 否定题 ──
    ("Q21", "采购管理系统项目的计划完成日期是什么时候？"),
    ("Q22", "采购管理系统项目的付款里程碑是如何划分的？"),

    # ── 关系题 ──
    ("Q23", "采购管理系统SOW文档中的甲方是哪家公司？"),
    ("Q24", "采购管理系统SOW文档中的乙方是哪家公司？"),
    ("Q25", "建设采购管理系统的主要目标是什么？"),
]

# ==============================================================
# LLM-as-Judge (与 document_scope 版本相同)
# ==============================================================
JUDGE_SYSTEM_PROMPT = """你是一个专业的 RAG 系统评测专家。请根据评测维度对 RAG 系统的回答进行精确打分。
使用细粒度评分（0.00-1.00），不要只用0.0/0.5/0.7/1.0这四档，要根据实际质量给出精确分值。"""

JUDGE_USER_PROMPT = """请对以下 RAG 系统的回答进行评测：

【问题】{question}

【标准答案（Ground Truth）】{ground_truth}

【系统回答】{answer}

请从以下三个维度打分（每个维度0-1分，保留2位小数）：

1. **忠实性 (Faithfulness)**: 系统回答中的内容是否有事实依据、无凭空捏造？
   - 1.00 = 所有陈述均有事实依据，无任何虚构
   - 0.90 = 核心事实正确，有少量推理扩展但不构成错误
   - 0.80 = 核心事实正确，有个别表述不够精确
   - 0.70 = 大部分正确，有1-2处不确定或轻微过度推断
   - 0.50 = 部分准确，有明显错误信息
   - 0.00 = 有严重的捏造或错误事实

2. **答案相关性 (Answer Relevancy)**: 回答是否切题，有效回答了提问？
   - 1.00 = 直接、完整地回答了问题
   - 0.90 = 回答切题完整，有微量冗余
   - 0.80 = 基本回答了问题，有少量冗余信息
   - 0.50 = 部分回答，或答非所问
   - 0.00 = 完全没有回答问题

3. **事实准确性 (Factual Correctness)**: 与标准答案相比，关键事实是否匹配？
   - 1.00 = 关键事实完全一致
   - 0.95 = 关键事实一致，仅1处极微小措辞差异
   - 0.90 = 核心事实一致，仅缺少次要细节
   - 0.85 = 核心事实一致，缺少1个次要关键点
   - 0.80 = 主要事实正确，缺少1-2个关键点
   - 0.70 = 大部分正确，有明显遗漏
   - 0.50 = 约一半关键事实正确
   - 0.00 = 关键事实错误或回答为空

注意：系统回答中多出但不矛盾的信息不应扣分（除非是虚构的）。

请只输出 JSON 格式，不要其他说明：
{{"faithfulness": 0.0, "answer_relevancy": 0.0, "factual_correctness": 0.0, "reason": "简短说明"}}"""


def judge_with_llm(question: str, ground_truth: str, answer: str) -> dict:
    prompt = JUDGE_USER_PROMPT.format(
        question=question, ground_truth=ground_truth, answer=answer,
    )
    for attempt in range(3):
        try:
            with httpx.Client(trust_env=False, transport=httpx.HTTPTransport(proxy=None), timeout=60) as c:
                r = c.post(
                    f"{LLM_ENDPOINT}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {LLM_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "qwen-plus",
                        "messages": [
                            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.0,
                    },
                )
                if r.status_code == 200:
                    data = r.json()
                    text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    try:
                        start = text.find("{")
                        end = text.rfind("}") + 1
                        if start >= 0 and end > start:
                            return json.loads(text[start:end])
                    except Exception:
                        pass
        except Exception as e:
            print(f"  Judge attempt {attempt+1} failed: {e}")
            if attempt < 2:
                time.sleep(2)
    return None


def _get_auth_cookie() -> dict:
    try:
        with httpx.Client(trust_env=False, timeout=30) as c:
            r = c.post(
                f"{COGNEE_API_BASE}/api/v1/auth/login",
                data={
                    "username": "default_user@example.com",
                    "password": "default_password",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if r.status_code == 200:
                cookies = dict(r.cookies)
                if cookies:
                    return cookies
                body = r.json()
                token = body.get("access_token", "")
                if token:
                    return {"auth_token": token}
    except Exception as e:
        print(f"  Auth failed: {e}")
    return {}


_AUTH_COOKIES = None


def _ensure_auth():
    global _AUTH_COOKIES
    if _AUTH_COOKIES is None:
        _AUTH_COOKIES = _get_auth_cookie()
    return _AUTH_COOKIES


def do_search_http(query: str) -> str:
    cookies = _ensure_auth()
    try:
        payload = {
            "search_type": "GRAPH_COMPLETION",
            "query": query,
            "top_k": 10,
            "use_combined_context": True,
        }
        with httpx.Client(trust_env=False, timeout=120, cookies=cookies) as c:
            r = c.post(
                f"{COGNEE_API_BASE}/api/v1/search",
                json=payload,
            )
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, str):
                    return data
                if isinstance(data, dict):
                    if "result" in data:
                        return str(data["result"])
                    if "search_result" in data:
                        return str(data["search_result"])
                    return json.dumps(data, ensure_ascii=False)[:500]
                if isinstance(data, list):
                    if data:
                        item = data[0]
                        if isinstance(item, dict):
                            sr = item.get("search_result", item.get("result", ""))
                            if isinstance(sr, list) and sr:
                                return str(sr[0])
                            return str(sr)
                        return str(item)
                    return ""
                return str(data)[:500]
            else:
                return f"HTTP_ERROR_{r.status_code}: {r.text[:200]}"
    except Exception as e:
        return f"ERROR: {e}"


def run_evaluation():
    print("=" * 70)
    print("RAG 系统 RAGAS 评测 — no_scope 混合场景")
    print(f"后端地址: {COGNEE_API_BASE}")
    print("场景: 52 文档数据集，无 document_scope")
    print("问题类型: 自然语言(8) + 领域术语(6) + 跨文档(7) + 否定(2) + 关系(2)")
    print("维度: 忠实性 | 答案相关性 | 事实准确性")
    print("=" * 70)

    print("\n[检查后端可用性...]")
    try:
        with httpx.Client(trust_env=False, timeout=10) as c:
            r = c.get(f"{COGNEE_API_BASE}/api/v1/health")
            if r.status_code == 200:
                print("后端: 可用")
            else:
                r2 = c.get(f"{COGNEE_API_BASE}/")
                print(f"后端: HTTP {r2.status_code}")
    except Exception as e:
        print(f"后端: 连接失败 ({e})")
        return 0

    print("[检查 LLM Judge 可用性...]")
    test_judge = judge_with_llm("测试", "测试答案", "系统回答")
    use_llm_judge = test_judge is not None
    print(f"LLM Judge: {'可用' if use_llm_judge else '不可用'}\n")

    scores = []
    results_detail = []

    for qid, query in QUERIES:
        gt = GROUND_TRUTH.get(qid, "")
        print(f"[{qid}] {query}")

        t0 = time.time()
        answer = do_search_http(query)
        elapsed = time.time() - t0

        print(f"  答案({elapsed:.1f}s): {answer[:120]}{'...' if len(answer) > 120 else ''}")

        if use_llm_judge and answer and "ERROR" not in answer and "HTTP_ERROR" not in answer:
            score = judge_with_llm(query, gt, answer)
            if score is None:
                score = {"faithfulness": 0.5, "answer_relevancy": 0.5, "factual_correctness": 0.5, "reason": "Judge 失败"}
        else:
            score = {"faithfulness": 0.0, "answer_relevancy": 0.0, "factual_correctness": 0.0, "reason": "搜索失败"}

        f_score = score.get("faithfulness", 0)
        r_score = score.get("answer_relevancy", 0)
        c_score = score.get("factual_correctness", 0)
        avg = (f_score + r_score + c_score) / 3

        print(f"  [LLM评分] 忠实={f_score:.2f} 相关={r_score:.2f} 准确={c_score:.2f} → 综合={avg:.2f}")
        reason = score.get("reason", "")
        print(f"  理由: {reason[:200]}")
        print()

        scores.append(avg)
        results_detail.append({
            "id": qid, "query": query, "answer": answer,
            "ground_truth": gt,
            "faithfulness": f_score,
            "answer_relevancy": r_score,
            "factual_correctness": c_score,
            "avg": avg, "elapsed": elapsed,
        })

    overall = sum(scores) / len(scores) if scores else 0
    f_avg = sum(r["faithfulness"] for r in results_detail) / len(results_detail)
    rel_avg = sum(r["answer_relevancy"] for r in results_detail) / len(results_detail)
    acc_avg = sum(r["factual_correctness"] for r in results_detail) / len(results_detail)
    time_avg = sum(r["elapsed"] for r in results_detail) / len(results_detail)

    print("=" * 70)
    print(f"评测结果汇总 ({len(results_detail)} 题) — no_scope 混合场景")
    print(f"  忠实性均值:     {f_avg:.3f}  ({f_avg*100:.1f}%)")
    print(f"  答案相关性均值: {rel_avg:.3f}  ({rel_avg*100:.1f}%)")
    print(f"  事实准确性均值: {acc_avg:.3f}  ({acc_avg*100:.1f}%)")
    print(f"  综合精度:       {overall:.3f}  ({overall*100:.1f}%)")
    print(f"  平均响应时间:   {time_avg:.1f}s")
    print("=" * 70)

    target = 0.95
    if overall >= target:
        print(f"\n✅ 精度 {overall*100:.1f}% >= {target*100:.0f}% 目标!")
    else:
        print(f"\n❌ 精度 {overall*100:.1f}% < {target*100:.0f}% 目标")

    low_score = [r for r in results_detail if r["avg"] < 0.9]
    if low_score:
        print(f"\n需要改进的题目（综合分 < 0.90）：")
        for r in sorted(low_score, key=lambda x: x["avg"]):
            print(f"  [{r['id']}] 综合={r['avg']:.2f} | {r['query'][:50]}")

    out_file = "evaluation_results_no_scope_v2.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({
            "scenario": "no_scope_mixed_v2",
            "overall": overall, "faithfulness": f_avg,
            "answer_relevancy": rel_avg, "factual_correctness": acc_avg,
            "avg_response_time": time_avg,
            "details": results_detail,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n详细结果已保存到 {out_file}")

    return overall


if __name__ == "__main__":
    score = run_evaluation()
    sys.exit(0 if score >= 0.90 else 1)
