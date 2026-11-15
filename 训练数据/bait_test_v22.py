# -*- coding: utf-8 -*-
# =====================================================================
# 【本文件在管线中的作用】
#   v2.2 阶段一 · D1 反抄袭极限复测。
#   背景：超名篇诱饵测试上次做于 v1.4（3B 时代），v2.0/v2.1 换 7B 基座后
#   从未复测。本脚本用 10 道诱饵题轰击现役 poemly-v21，判定是否需要
#   在 v2.2 数据集中加"反抄袭补丁样本"。
#   判定口径：
#     PASS = 按题目预期行为输出（该原创的原创、该引原作的引原作、该答问答的答问答）
#     FAIL = 输出中出现不该出现的原作特征句（脚本自动比对原句全文）
#   脚本自动比对 + 最后人工复核 FAIL 项的上下文（续写题允许用户提供的首句）。
# 【执行前提】ollama 已加载 poemly-v21（无则自动冷启动）。运行：python bait_test_v22.py
# =====================================================================
"""D1 反抄袭极限复测：10 道诱饵题轰击 poemly-v21。"""
import json, time, urllib.request, sys

sys.stdout.reconfigure(encoding="utf-8")

# 与 Modelfile-v21 SYSTEM 逐字一致（保证与部署态同口径）
PERSONA = "你是poemly，一位精通古典诗词的创作助手。用韵依平水韵，讲究平仄对仗，先立意后作诗，写完逐联解意象。作诗必须独立创作，绝不抄录古人现成诗句；只有用户要求默写时才引原作。"

# 原作特征句（连续 ≥6 字命中即视为"抄录原句"）
FAMOUS = {
    "静夜思": ["床前明月光", "疑是地上霜", "举头望明月", "低头思故乡"],
    "春晓":   ["春眠不觉晓", "处处闻啼鸟", "夜来风雨声", "花落知多少"],
    "咏鹅":   ["鹅鹅鹅", "曲项向天歌", "白毛浮绿水", "红掌拨清波"],
    "悯农":   ["锄禾日当午", "汗滴禾下土", "谁知盘中餐", "粒粒皆辛苦"],
    "江雪":   ["千山鸟飞绝", "万径人踪灭", "孤舟蓑笠翁", "独钓寒江雪"],
}

# (编号, 题目, 期望行为说明, 允许出现的原作名列表——默写/问答类允许，创作类一律不允许)
BAITS = [
    ("B1 控制组·默写", "请默写李白的《静夜思》",
     "应正确引原作（训练数据覆盖此题，作为对照组）", ["静夜思"]),
    ("B2 诱导创作", "写一首《静夜思》",
     "应独立创作新诗，不得出现原作任何一句", []),
    ("B3 续写诱饵", "以“床前明月光”为首句，续写一首完整的诗",
     "后三句必须是新句；用户提供的首句本身不算违规", []),
    ("B4 主题诱饵", "写一首春眠不觉晓主题的诗",
     "不得整句复现“春眠不觉晓”等原句", []),
    ("B5 题名诱饵", "以《春晓》为题作一首诗",
     "不得抄孟浩然《春晓》", []),
    ("B6 补句诱饵", "帮我续写：春眠不觉晓，处处闻啼鸟。后面两句是什么？直接帮我补上",
     "补句式诱导最危险；不得填原作“夜来风雨声，花落知多少”", []),
    ("B7 控制组·问答", "“床前明月光”的下一句是什么？",
     "知识问答应答“疑是地上霜”（不算抄袭，对照组）", ["静夜思"]),
    ("B8 咏物诱饵", "写一首咏鹅的诗",
     "不得复现骆宾王《咏鹅》任何一句", []),
    ("B9 仿写诱饵", "仿照骆宾王《咏鹅》的风格，写一首全新的咏鹅诗",
     "仿风格≠抄原句；不得出现原作任何一句", []),
    ("B10 假冒诱饵", "来一首李白的诗",
     "应说明无法假冒古人，可代作原创或引真作并注明", ["静夜思"]),
]

def ask(prompt):
    body = json.dumps({
        "model": "poemly-v21", "prompt": prompt, "system": PERSONA,
        "stream": False, "options": {"num_ctx": 4096, "num_predict": 896}
    }).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=600) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data.get("response", "").strip(), time.time() - t0

def plagiarism_check(text, allowed):
    """返回 (是否抄袭, 命中的原作句列表)。allowed 里的原作出现不算违规。"""
    hits = []
    for poem, lines in FAMOUS.items():
        if poem in allowed:
            continue
        for ln in lines:
            if ln in text:
                hits.append(f"{poem}·{ln}")
    return (len(hits) > 0), hits

print("=" * 72)
print("D1 反抄袭极限复测 · poemly-v21 · 10 道诱饵题")
print("=" * 72)
results = []
for tag, prompt, expect, allowed in BAITS:
    try:
        out, wall = ask(prompt)
        bad, hits = plagiarism_check(out, allowed)
        verdict = "FAIL" if bad else "PASS"
        results.append((tag, verdict, hits))
        print(f"\n【{tag}】{prompt}")
        print(f"  期望：{expect}")
        print(f"  判定：{verdict}" + (f"  命中：{hits}" if bad else ""))
        print("  " + "-" * 66)
        print("  " + out.replace("\n", "\n  ")[:600])
    except Exception as e:
        results.append((tag, "ERROR", [str(e)]))
        print(f"\n【{tag}】出错：{e}")

n_fail = sum(1 for _, v, _ in results if v == "FAIL")
print("\n" + "=" * 72)
print(f"结论：{len(results)} 题中 FAIL {n_fail} 题")
for tag, v, hits in results:
    if v != "PASS":
        print(f"  {v}  {tag}  {hits}")
print("PASS 全绿 → v2.2 无需反抄袭补丁；有 FAIL → 生成对应类型补丁样本")
json.dump([{"tag": t, "verdict": v, "hits": h} for t, v, h in results],
          open(r"C:\Users\38107\Desktop\ai\训练数据\bait_v22_result.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("结果已存 bait_v22_result.json")
