# -*- coding: utf-8 -*-
"""
通过 HTTP API 调用 cognee 后端的 RAGAS 评测脚本
不需要 cognee SDK 依赖，只需要 httpx
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
# Ground Truth
# ==============================================================
GROUND_TRUTH = {
    "Q01": "优化采购流程，提升信息化管理水平，构建采购管理系统实现全流程管控；通过对接NC系统、支持移动端操作、加强供应商管理与采购需求动态监控，降低采购成本，提升采购效率",
    "Q02": "本项目系统最多允许2000名用户访问（访问用户不超过2000人，集团公司一级组织）",
    "Q03": "V1.1",
    "Q04": "文档中未明确给出项目计划完成日期",
    "Q05": "山东正和热电有限公司",
    "Q06": "山东佳航智能科技有限公司",
    "Q07": "AWS PaaS 6.4.GA（实例安装版，非集群）",
    "Q08": "本项目SOW文档中未明确规定付款里程碑的具体划分方式、付款比例或付款时间节点",
    "Q09": "乙方职责：提供采购系统实施服务、培训甲方技术人员（AIE/ADE工程师培训）、执行项目交付；甲方职责：提供硬件环境和办公条件、配合接口开发联调、确保项目组专职人员有决策权、主导多厂商协同",
    "Q10": "项目交付文档包括工作说明书（SOW）等；甲乙双方各自任命项目经理作为授权代表签核交付文档；所有系统实施交付文档用中文编写",
    "Q11": "用友NC6.5（ERP系统，涉及11类业务数据集成）和钉钉（移动审批平台）",
    "Q12": "没有严重缺陷及甲方不可接受的中等缺陷；各方已同意并拟定处理遗留缺陷的期限及计划；系统上线验收以系统上线申请报告签批完成为标志；最终验收在系统上线运行3个月内完成",
    "Q13": "服务范围包括：采购管理端模块和供应商端功能的流程实施（17个流程）；AWS PaaS平台部署；与NC6.5和钉钉的系统集成（涉及11类业务数据）；AIE/ADE工程师培训及认证；上线后两个月支持保障；基础维保（MA）服务",
    "Q14": "供应商注册审核（准入审核、多级审批）、供应商档案管理（基本信息/联系方式/银行账户/资质证书）、供应商分类管理、供应商评价（物流时效/产品质量等维度打分）",
    "Q15": "填写采购需求申请表单→系统查询库存（对接NC）→自动匹配流程分支→可选加急流程→支持平库操作→上传附件→流程完成后进入需求台账，后续可发起询比价或招标",
    "Q16": "17个流程",
    "Q17": "订单管理包含3个子功能：采购订单（从合同导入或手动填写、审批后推送NC）、到货通知单（供应商发货后仓库生成）、验货申请单（仓库发起验货申请、审批后采购入库推送NC）",
    "Q18": "AWS PaaS控制台仅支持A级浏览器（IE10+、Chrome35+、Firefox30+）；AWS PaaS客户端同时支持A、B级浏览器（B级含IE8/9，不推荐）；IE必须运行在非兼容性模式；分辨率不低于1024×768",
    "Q19": "AIE工程师培训、ADE工程师培训、AIE/ADE认证考试；乙方每季度举办公开课，免费参加，通过后颁发证书；甲方也负责对最终用户进行操作培训",
    "Q20": "合同审批流程：填报界面（支持手动填写或从推荐供应商台账自动带入供应商、物料、价格等信息）→上传附件→提交审批或保存草稿→审批通过后生成合同台账",
    "Q21": "合同变更管理流程：提出变更请求报告→双方项目经理签字批准→内部存档并提报项目指导委员会；涉及费用或进展的变更须经项目实施领导小组批准；系统中可发起变更申请并经审批生成新版本合同",
    "Q22": "系统上线后两个月内提供现场和远程支持（质保期支持），包含问题修正及操作支持；另有基础维保服务（MA）从合同签署满一年后开始",
    "Q23": "在供应商平台→订单管理→查询采购方订单→关联订单发起发货单→填写发货物料信息、规格型号、数量等关键字段",
    "Q24": "两种形式：分项验收（需求设计验收、系统上线验收，按里程碑阶段进行）和最终验收（系统上线运行3个月内）",
    "Q25": "五个阶段：项目准备（目标定义）→蓝图设计（目标分解）→系统建设（目标实现）→上线验收（客户价值实现）→上线支持（投资收益最大化）",
}

QUERIES = [
    ("Q01", "本项目的主要目标是什么？"),
    ("Q02", "本项目系统最多允许多少名用户访问？"),
    ("Q03", "本项目工作说明书的文档版本号是多少？"),
    ("Q04", "项目的计划完成日期是什么时候？"),
    ("Q05", "本SOW文档的甲方是谁？"),
    ("Q06", "本SOW文档的乙方是谁？"),
    ("Q07", "项目环境要求表中AWS PaaS的版本号是多少？"),
    ("Q08", "项目的付款里程碑是如何划分的？"),
    ("Q09", "项目实施过程中，乙方和甲方各自的主要职责是什么？"),
    ("Q10", "项目的交付文档有什么要求？"),
    ("Q11", "系统需要集成哪些外部系统？"),
    ("Q12", "项目的验收标准是什么？"),
    ("Q13", "本项目的服务范围包括哪些内容？"),
    ("Q14", "供应商管理模块有哪些主要功能？"),
    ("Q15", "采购申请流程是怎样的？"),
    ("Q16", "本项目一共实施多少个流程？"),
    ("Q17", "订单管理模块包含哪些子功能？"),
    ("Q18", "系统需要满足哪些客户端浏览器要求？"),
    ("Q19", "项目的培训范围包括哪些内容？"),
    ("Q20", "合同审批流程的主要步骤是什么？"),
    ("Q21", "合同变更管理的流程是什么？"),
    ("Q22", "系统上线后的运维支持期限是多久？"),
    ("Q23", "供应商端如何填写发货单？"),
    ("Q24", "项目验收有哪几种形式？"),
    ("Q25", "项目实施的总体计划分为几个阶段？"),
]

# ==============================================================
# LLM-as-Judge
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
   - 0.90 = 核心事实一致，仅缺少次要细节
   - 0.80 = 主要事实正确，缺少1-2个关键点
   - 0.70 = 大部分正确，有明显遗漏
   - 0.50 = 约一半关键事实正确
   - 0.00 = 关键事实错误或回答为空

注意：系统回答中多出但不矛盾的信息不应扣分（除非是虚构的）。

请只输出 JSON 格式，不要其他说明：
{{"faithfulness": 0.0, "answer_relevancy": 0.0, "factual_correctness": 0.0, "reason": "简短说明"}}"""


def judge_with_llm(question: str, ground_truth: str, answer: str) -> dict:
    """使用 DashScope LLM API 对答案进行 RAGAS 风格评分"""
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
                continue
    return None


def _get_auth_cookie() -> dict:
    """Login and get auth cookie for API calls."""
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
                # Fallback: extract token from response body
                body = r.json()
                token = body.get("access_token", "")
                if token:
                    return {"auth_token": token}
    except Exception as e:
        print(f"  Auth failed: {e}")
    return {}


# Module-level auth cookie (lazy init)
_AUTH_COOKIES = None


def _ensure_auth():
    global _AUTH_COOKIES
    if _AUTH_COOKIES is None:
        _AUTH_COOKIES = _get_auth_cookie()
    return _AUTH_COOKIES


def do_search_http(query: str) -> str:
    """通过 HTTP API 调用 cognee 搜索"""
    cookies = _ensure_auth()
    try:
        with httpx.Client(trust_env=False, timeout=120, cookies=cookies) as c:
            r = c.post(
                f"{COGNEE_API_BASE}/api/v1/search",
                json={
                    "search_type": "GRAPH_COMPLETION",
                    "query": query,
                    "top_k": 10,
                    "use_combined_context": True,
                },
            )
            if r.status_code == 200:
                data = r.json()
                # The response could be various formats
                if isinstance(data, str):
                    return data
                if isinstance(data, dict):
                    # Check for result field
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
    print("RAG 系统 RAGAS 风格评测 (HTTP API)")
    print(f"后端地址: {COGNEE_API_BASE}")
    print("维度: 忠实性 | 答案相关性 | 事实准确性")
    print("=" * 70)

    # Check backend availability
    print("\n[检查后端可用性...]")
    try:
        with httpx.Client(trust_env=False, timeout=10) as c:
            r = c.get(f"{COGNEE_API_BASE}/api/v1/health")
            if r.status_code == 200:
                print(f"后端: 可用")
            else:
                # Try root
                r2 = c.get(f"{COGNEE_API_BASE}/")
                print(f"后端: HTTP {r2.status_code}")
    except Exception as e:
        print(f"后端: 连接失败 ({e})")
        print("请确认后端服务已启动在 http://localhost:8000")
        return 0

    # Check LLM judge
    print("[检查 LLM Judge 可用性...]")
    test_judge = judge_with_llm("测试", "测试答案", "系统回答")
    use_llm_judge = test_judge is not None
    print(f"LLM Judge: {'可用' if use_llm_judge else '不可用，使用规则评分'}\n")

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
                score = _rule_based_judge(query, gt, answer)
                score_method = "规则"
            else:
                score_method = "LLM"
        else:
            score = _rule_based_judge(query, gt, answer)
            score_method = "规则"

        f_score = score.get("faithfulness", 0)
        r_score = score.get("answer_relevancy", 0)
        c_score = score.get("factual_correctness", 0)
        avg = (f_score + r_score + c_score) / 3

        print(f"  [{score_method}评分] 忠实={f_score:.2f} 相关={r_score:.2f} 准确={c_score:.2f} → 综合={avg:.2f}")
        print(f"  理由: {score.get('reason', '')}")
        print()

        scores.append(avg)
        results_detail.append({
            "id": qid, "query": query, "answer": answer,
            "ground_truth": gt,
            "faithfulness": f_score,
            "answer_relevancy": r_score,
            "factual_correctness": c_score,
            "avg": avg, "method": score_method, "elapsed": elapsed,
        })

    overall = sum(scores) / len(scores) if scores else 0
    f_avg = sum(r["faithfulness"] for r in results_detail) / len(results_detail)
    rel_avg = sum(r["answer_relevancy"] for r in results_detail) / len(results_detail)
    acc_avg = sum(r["factual_correctness"] for r in results_detail) / len(results_detail)
    time_avg = sum(r["elapsed"] for r in results_detail) / len(results_detail)

    print("=" * 70)
    print(f"评测结果汇总 ({len(results_detail)} 题)")
    print(f"  忠实性均值:     {f_avg:.3f}  ({f_avg*100:.1f}%)")
    print(f"  答案相关性均值: {rel_avg:.3f}  ({rel_avg*100:.1f}%)")
    print(f"  事实准确性均值: {acc_avg:.3f}  ({acc_avg*100:.1f}%)")
    print(f"  综合精度:       {overall:.3f}  ({overall*100:.1f}%)")
    print(f"  平均响应时间:   {time_avg:.1f}s")
    print("=" * 70)

    target = 0.93
    if overall >= target:
        print(f"\n✅ 精度 {overall*100:.1f}% >= {target*100:.0f}% 目标, Phase B 验证通过!")
    else:
        print(f"\n❌ 精度 {overall*100:.1f}% < {target*100:.0f}% 目标, 需要调查原因")

    low_score = [r for r in results_detail if r["avg"] < 0.6]
    if low_score:
        print(f"\n需要改进的题目（综合分 < 0.6）：")
        for r in sorted(low_score, key=lambda x: x["avg"]):
            print(f"  [{r['id']}] 综合={r['avg']:.2f} | {r['query']}")

    with open("evaluation_results_phase_b.json", "w", encoding="utf-8") as f:
        json.dump({
            "overall": overall, "faithfulness": f_avg,
            "answer_relevancy": rel_avg, "factual_correctness": acc_avg,
            "avg_response_time": time_avg,
            "details": results_detail,
            "note": "Phase B dual-model (qwen-turbo extraction, qwen-plus answer)",
        }, f, ensure_ascii=False, indent=2)
    print("\n详细结果已保存到 evaluation_results_phase_b.json")

    return overall


def _rule_based_judge(question: str, ground_truth: str, answer: str) -> dict:
    import re
    answer_lower = answer.lower()
    gt_lower = ground_truth.lower()

    no_info_phrases = ["未找到相关信息", "没有找到", "无法回答", "暂无资料"]
    gt_not_available_phrases = ["未明确", "未规定", "未给出", "未提及", "没有规定"]
    answer_says_not_found = any(p in answer for p in no_info_phrases)
    gt_says_not_available = any(p in gt_lower for p in gt_not_available_phrases)

    if answer_says_not_found and gt_says_not_available:
        return {"faithfulness": 1.0, "answer_relevancy": 1.0, "factual_correctness": 1.0,
                "reason": "系统正确指出信息不在文档中"}
    if answer_says_not_found:
        return {"faithfulness": 0.5, "answer_relevancy": 0.0, "factual_correctness": 0.0,
                "reason": "系统返回'未找到相关信息'"}

    gt_numbers = re.findall(r'\d+(?:\.\d+)?', gt_lower)
    gt_entities = re.findall(r'[\u4e00-\u9fff]{2,10}', gt_lower)
    gt_entities = [e for e in gt_entities if len(e) >= 2][:10]
    all_gt_terms = gt_numbers + gt_entities[:5]

    if all_gt_terms:
        hits = sum(1 for t in all_gt_terms if t in answer_lower)
        factual = hits / len(all_gt_terms)
    else:
        hits = 0
        factual = 0.5

    relevancy = min(0.9, 0.5 + factual * 0.4) if len(answer.strip()) > 30 else (0.5 if len(answer.strip()) > 10 else 0.1)
    faithfulness = 0.8 if len(answer.strip()) > 20 else 0.5

    return {"faithfulness": round(faithfulness, 2), "answer_relevancy": round(relevancy, 2),
            "factual_correctness": round(min(factual, 1.0), 2),
            "reason": f"规则评分: 命中 {hits}/{len(all_gt_terms)}"}


if __name__ == "__main__":
    score = run_evaluation()
    sys.exit(0 if score >= 0.75 else 1)
