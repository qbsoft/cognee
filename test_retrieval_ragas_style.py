# -*- coding: utf-8 -*-
"""
RAGAS 风格的 RAG 评测脚本
评测维度:
  - Faithfulness (忠实性): 答案是否基于检索内容，无幻觉
  - Answer Relevancy (答案相关性): 答案是否真正回答了问题
  - Factual Correctness (事实准确性): 答案与已知正确答案的一致性
综合得分 = 三维平均

使用 LLM 作为裁判 (LLM-as-Judge)
"""
import sys, io, httpx, json, time, asyncio
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

BASE_URL = "http://127.0.0.1:8000"

# ==============================================================
# Ground Truth: 从文档原文提取的标准答案
# ==============================================================
GROUND_TRUTH = {
    "Q01": "优化采购流程，提升信息化管理水平，构建采购管理系统实现全流程管控；通过对接NC系统、支持移动端操作、加强供应商管理与采购需求动态监控，降低采购成本，提升采购效率",
    "Q02": "本项目系统最多允许2000名用户访问（访问用户不超过2000人，集团公司一级组织）",
    "Q03": "V1.1",
    "Q04": "文档中未明确给出项目计划完成日期",
    "Q05": "山东正和热电有限公司",
    "Q06": "山东佳航智能科技有限公司",
    "Q07": "AWS PaaS 6.4.GA（实例安装版，非集群）",
    "Q08": "本项目SOW文档未明确规定付款里程碑比例或时间节点；项目实施分为五个阶段：项目准备、蓝图设计、系统建设、上线验收、上线支持",
    "Q09": "乙方职责：提供采购系统实施服务、培训甲方技术人员（AIE/ADE工程师培训）、执行项目交付；甲方职责：提供硬件环境和办公条件、配合接口开发联调、确保项目组专职人员有决策权、主导多厂商协同",
    "Q10": "需求分析阶段主要交付物包括：详细需求说明文档（各模块功能需求描述）、工作说明书（SOW，如PM_P0_06工作说明书等），以及相关功能规格和业务流程说明文档等",
    "Q11": "用友NC6.5（ERP系统，涉及11类业务数据集成）和钉钉（移动审批平台）",
    "Q12": "没有严重缺陷及甲方不可接受的中等缺陷；各方已同意并拟定处理遗留缺陷的期限及计划；系统上线验收以系统上线申请报告签批完成为标志；最终验收在系统上线运行3个月内完成",
    "Q13": "本项目服务范围8项：17个采购管理业务流程实施；AWS PaaS 6.4.GA平台部署（实例安装版，非集群）；用友NC6.5和钉钉系统集成（涉及11类业务数据）；AIE/ADE工程师培训及认证；上线后2个月质保期支持；基础维保（MA）服务（合同满一年后起）；支持不超过2000名用户；7×24小时后台监控",
    "Q14": "供应商注册审核（准入审核、多级审批）、供应商档案管理（基本信息/联系方式/银行账户/资质证书）、供应商分类管理、供应商评价（物流时效/产品质量等维度打分）",
    "Q15": "填写采购需求申请表单→系统查询库存（对接NC）→自动匹配流程分支→可选加急流程→支持平库操作→上传附件→流程完成后进入需求台账，后续可发起询比价或招标",
    "Q16": "17个流程",
    "Q17": "订单管理包含2个子流程：①采购订单流程（从合同导入或手动填写、经审批后推送NC系统，供应商可查询订单和填写发货单）；②验货申请流程（供应商发货→仓库生成到货通知单→仓库发起验货申请单→审批→采购入库）",
    "Q18": "AWS PaaS控制台仅支持A级浏览器（IE10+、Chrome35+、Firefox30+）；AWS PaaS客户端同时支持A、B级浏览器（B级含IE8/9，不推荐）；IE必须运行在非兼容性模式；分辨率不低于1024×768",
    "Q19": "AIE工程师培训、ADE工程师培训、AIE/ADE认证考试；乙方每季度举办公开课，免费参加，通过后颁发证书；甲方也负责对最终用户进行操作培训",
    "Q20": "合同审批流程：填报界面（支持手动填写或从推荐供应商台账自动带入供应商、物料、价格等信息）→上传附件→提交审批或保存草稿→审批通过后生成合同台账",
    "Q21": "合同变更流程（序号6，合同管理类别）：针对已签合同进行修改、补充或终止的处理流程，属于合同管理全生命周期的重要环节",
    "Q22": "系统上线后2个月内提供现场和远程支持（质保期支持）；基础维保服务（MA）从合同签署满一年后开始（与2个月质保是两种不同服务）",
    "Q23": "在供应商平台→订单管理→查询采购方订单→关联订单发起发货单→填写发货物料信息、规格型号、数量等关键字段",
    "Q24": "两种形式：分项验收（需求设计验收、系统上线验收，按里程碑阶段进行）和最终验收（系统上线运行3个月内）",
    "Q25": "五个阶段：项目准备（目标定义）→蓝图设计（目标分解）→系统建设（目标实现）→上线验收（客户价值实现）→上线支持（投资收益最大化）",
}

# ==============================================================
# 测试用查询（比之前更精准）
# ==============================================================
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
    ("Q10", "需求分析阶段的主要交付物有哪些？"),
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
# LLM-as-Judge 评分 Prompt
# ==============================================================
JUDGE_SYSTEM_PROMPT = """你是一个专业的 RAG 系统评测专家。你的任务是根据给定的评测维度，对 RAG 系统的回答进行打分。
评分规则严格，不要给出过高的分数，要区分"完全正确"和"基本正确"的差别。"""

JUDGE_USER_PROMPT = """请对以下 RAG 系统的回答进行评测：

【问题】{question}

【标准答案（Ground Truth）】{ground_truth}

【系统回答】{answer}

请从以下三个维度打分（每个维度0-1分，保留2位小数）：

1. **忠实性 (Faithfulness)**: 系统回答中的内容是否有事实依据、无凭空捏造？
   - 1.0 = 完全基于事实，无幻觉
   - 0.7 = 基本准确，有轻微不确定表述
   - 0.5 = 部分准确，有明显不确定或轻微错误
   - 0.0 = 有严重的捏造或错误事实

2. **答案相关性 (Answer Relevancy)**: 回答是否切题，有效回答了提问？
   - 1.0 = 直接、完整地回答了问题
   - 0.7 = 基本回答了问题，有少量冗余
   - 0.5 = 部分回答，或答非所问
   - 0.0 = 完全没有回答问题（如"未找到相关信息"）

3. **事实准确性 (Factual Correctness)**: 与标准答案相比，关键事实是否正确？
   - 1.0 = 关键事实完全一致
   - 0.7 = 大部分关键事实正确，有少量遗漏
   - 0.5 = 一半左右关键事实正确
   - 0.0 = 关键事实错误或回答为空

请只输出 JSON 格式，不要其他说明：
{{"faithfulness": 0.0, "answer_relevancy": 0.0, "factual_correctness": 0.0, "reason": "简短说明"}}"""


def get_token():
    with httpx.Client(trust_env=False, transport=httpx.HTTPTransport(proxy=None), timeout=30) as c:
        r = c.post(
            f"{BASE_URL}/api/v1/auth/login",
            data={"username": "default_user@example.com", "password": "default_password"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        return r.json().get("access_token")


def search(query: str, auth_header: dict) -> str:
    with httpx.Client(trust_env=False, transport=httpx.HTTPTransport(proxy=None), timeout=120) as c:
        r = c.post(
            f"{BASE_URL}/api/v1/search",
            headers={**auth_header, "Content-Type": "application/json"},
            json={"query": query, "query_type": "GRAPH_COMPLETION", "top_k": 10,
                  "use_combined_context": True},
        )
        r.raise_for_status()
        data = r.json()
        # use_combined_context=True returns list with dict containing 'result' key
        if isinstance(data, list) and data:
            item = data[0]
            # Combined context mode returns dict with 'result' key
            if isinstance(item, dict):
                # Try 'search_result' first (standard mode), then 'result' (combined mode)
                sr = item.get("search_result", [])
                if sr:
                    return sr[0] if sr else ""
                # combined context mode: item might be {'result': ..., 'context': ...}
                result_val = item.get("result", "")
                if result_val and isinstance(result_val, str):
                    return result_val
                # or item might be a CombinedSearchResult serialized as dict with 'result' as top level
                if "result" in item:
                    return str(item["result"])[:500]
        # Handle case where data is a dict directly
        if isinstance(data, dict):
            return str(data.get("result", data.get("search_result", "")))[:500]
        return ""


DASHSCOPE_API_KEY = "sk-f9235546f8944cdca5529643bfa153f1"
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

def judge_with_llm(question: str, ground_truth: str, answer: str, auth_header: dict) -> dict:
    """使用 DashScope LLM API 对答案进行 RAGAS 风格评分（带重试）"""
    prompt = JUDGE_USER_PROMPT.format(
        question=question,
        ground_truth=ground_truth,
        answer=answer,
    )
    for attempt in range(3):
        try:
            with httpx.Client(trust_env=False, transport=httpx.HTTPTransport(proxy=None), timeout=60) as c:
                r = c.post(
                    f"{DASHSCOPE_BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
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
                    # 提取 JSON
                    try:
                        start = text.find("{")
                        end = text.rfind("}") + 1
                        if start >= 0 and end > start:
                            return json.loads(text[start:end])
                    except Exception:
                        pass
                else:
                    return None
        except Exception as e:
            if attempt < 2:
                time.sleep(2)
                continue
            return None
    return None


def rule_based_judge(question: str, ground_truth: str, answer: str) -> dict:
    """
    规则评分（当 LLM judge 不可用时的备选方案）
    基于关键词匹配 + 字符相似度
    """
    answer_lower = answer.lower()
    gt_lower = ground_truth.lower()

    # 检查是否为"未找到相关信息"（Answer Relevancy = 0）
    no_info_phrases = ["未找到相关信息", "没有找到", "无法回答", "暂无资料"]
    gt_not_available_phrases = ["未明确", "未规定", "未给出", "未提及", "没有规定", "不在sow", "未在文档"]
    answer_says_not_found = any(p in answer for p in no_info_phrases)
    gt_says_not_available = any(p in gt_lower for p in gt_not_available_phrases)
    # 若 GT 本身说"信息不在文档中"，系统回答"未找到"是正确的
    if answer_says_not_found and gt_says_not_available:
        return {
            "faithfulness": 1.0,
            "answer_relevancy": 1.0,
            "factual_correctness": 1.0,
            "reason": "系统正确指出信息不在文档中，与标准答案一致（GT也说未明确/未规定）"
        }
    if answer_says_not_found:
        return {
            "faithfulness": 0.5,
            "answer_relevancy": 0.0,
            "factual_correctness": 0.0,
            "reason": "系统返回'未找到相关信息'，未实际回答问题"
        }

    # 提取 Ground Truth 中的关键数字/专有名词
    import re
    gt_numbers = re.findall(r'\d+(?:\.\d+)?', gt_lower)
    gt_entities = re.findall(r'[\u4e00-\u9fff]{2,10}', gt_lower)
    gt_entities = [e for e in gt_entities if len(e) >= 2][:10]

    # 事实准确性：关键词命中率
    all_gt_terms = gt_numbers + gt_entities[:5]
    if all_gt_terms:
        hits = sum(1 for t in all_gt_terms if t in answer_lower)
        factual = hits / len(all_gt_terms)
    else:
        factual = 0.5

    # 答案相关性：答案长度和内容是否有实质内容
    if len(answer.strip()) < 10:
        relevancy = 0.1
    elif len(answer.strip()) > 30:
        relevancy = min(0.9, 0.5 + factual * 0.4)
    else:
        relevancy = 0.5

    # 忠实性：如果答案有具体内容，认为基本忠实
    faithfulness = 0.8 if len(answer.strip()) > 20 else 0.5

    return {
        "faithfulness": round(faithfulness, 2),
        "answer_relevancy": round(relevancy, 2),
        "factual_correctness": round(min(factual, 1.0), 2),
        "reason": f"规则评分: GT关键词命中 {hits if all_gt_terms else 'N/A'}/{len(all_gt_terms) if all_gt_terms else 0}"
    }


def run_evaluation():
    print("=" * 70)
    print("RAG 系统 RAGAS 风格评测")
    print("维度: 忠实性 | 答案相关性 | 事实准确性")
    print("=" * 70)

    token = get_token()
    auth_header = {"Authorization": f"Bearer {token}"}

    # 先测试 LLM judge 是否可用
    print("\n[检查 LLM Judge 可用性...]")
    test_judge = judge_with_llm("测试", "测试答案", "系统回答", auth_header)
    use_llm_judge = test_judge is not None
    print(f"LLM Judge: {'可用' if use_llm_judge else '不可用，使用规则评分'}\n")

    scores = []
    results_detail = []

    for qid, query in QUERIES:
        gt = GROUND_TRUTH.get(qid, "")
        print(f"[{qid}] {query}")

        # 获取答案
        try:
            t0 = time.time()
            answer = search(query, auth_header)
            elapsed = time.time() - t0
        except Exception as e:
            answer = f"ERROR: {e}"
            elapsed = 0

        print(f"  系统答案: {answer[:120]}{'...' if len(answer) > 120 else ''}")

        # 评分
        if use_llm_judge and answer and "ERROR" not in answer:
            score = judge_with_llm(query, gt, answer, auth_header)
            if score is None:
                score = rule_based_judge(query, gt, answer)
                score_method = "规则"
            else:
                score_method = "LLM"
        else:
            score = rule_based_judge(query, gt, answer)
            score_method = "规则"

        f_score = score.get("faithfulness", 0)
        r_score = score.get("answer_relevancy", 0)
        c_score = score.get("factual_correctness", 0)
        avg = (f_score + r_score + c_score) / 3
        reason = score.get("reason", "")

        print(f"  [{score_method}评分] 忠实={f_score:.2f} 相关={r_score:.2f} 准确={c_score:.2f} → 综合={avg:.2f}")
        print(f"  评分理由: {reason}")
        print()

        scores.append(avg)
        results_detail.append({
            "id": qid, "query": query, "answer": answer,
            "ground_truth": gt,
            "faithfulness": f_score,
            "answer_relevancy": r_score,
            "factual_correctness": c_score,
            "avg": avg,
            "method": score_method,
        })

    # 汇总
    overall = sum(scores) / len(scores) if scores else 0
    f_avg = sum(r["faithfulness"] for r in results_detail) / len(results_detail)
    rel_avg = sum(r["answer_relevancy"] for r in results_detail) / len(results_detail)
    acc_avg = sum(r["factual_correctness"] for r in results_detail) / len(results_detail)

    print("=" * 70)
    print(f"评测结果汇总 ({len(results_detail)} 题)")
    print(f"  忠实性均值:   {f_avg:.3f}  ({f_avg*100:.1f}%)")
    print(f"  答案相关性均值: {rel_avg:.3f}  ({rel_avg*100:.1f}%)")
    print(f"  事实准确性均值: {acc_avg:.3f}  ({acc_avg*100:.1f}%)")
    print(f"  综合精度:     {overall:.3f}  ({overall*100:.1f}%)")
    print("=" * 70)

    # 输出低分题
    low_score = [r for r in results_detail if r["avg"] < 0.6]
    if low_score:
        print(f"\n需要改进的题目（综合分 < 0.6）：")
        for r in sorted(low_score, key=lambda x: x["avg"]):
            print(f"  [{r['id']}] 综合={r['avg']:.2f} | {r['query']}")

    # 保存结果
    with open("evaluation_results.json", "w", encoding="utf-8") as f:
        json.dump({
            "overall": overall,
            "faithfulness": f_avg,
            "answer_relevancy": rel_avg,
            "factual_correctness": acc_avg,
            "details": results_detail,
        }, f, ensure_ascii=False, indent=2)
    print("\n详细结果已保存到 evaluation_results.json")

    return overall


if __name__ == "__main__":
    score = run_evaluation()
    sys.exit(0 if score >= 0.75 else 1)
