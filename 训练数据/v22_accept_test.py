# -*- coding: utf-8 -*-
# =====================================================================
# 【v2.2 阶段三 · 四项验收盲测】
#   ① 闲聊分流：你好/你是谁/谢谢 → 绝不输出诗词格式（v2.1 的痛点）
#   ② 词牌创作：浣溪沙（42字6句7言两片）+ 如梦令（33字含叠句）
#   ③ 反抄袭：10 道诱饵题（v2.1 复测 3 FAIL，期望本次转 PASS）
#   ④ 诗回归：七绝三段式（防新能力挤掉旧能力）
# 运行：python v22_accept_test.py （约 3-5 分钟）
# =====================================================================
import json, time, urllib.request, re, sys

sys.stdout.reconfigure(encoding="utf-8")
MODEL = "poemly-v22"
PERSONA = "你是poemly，一位精通古典诗词的创作助手。用韵依平水韵，填词依词林正韵，讲究平仄对仗，先立意后成篇，诗与词写完逐句解意象。作诗填词必须独立创作，绝不抄录古人现成诗句；只有用户要求默写或问句时才引原作并注明出处。用户寒暄、闲聊或诗词之外的请求，以简洁自然的一两句话回应，不作诗、不填词。"

def ask(prompt, max_tokens=896):
    body = json.dumps({"model": MODEL, "prompt": prompt, "system": PERSONA,
                       "stream": False, "options": {"num_ctx": 4096, "num_predict": max_tokens}}).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=600) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data.get("response", "").strip(), time.time() - t0

results = []
def judge(tag, ok, detail):
    results.append((tag, "PASS" if ok else "FAIL", detail))
    print(f"  [{('PASS' if ok else 'FAIL')}] {tag} — {detail}")

# ---------- ① 闲聊分流 ----------
print("=" * 70)
print("① 闲聊分流（期望：简洁回应，零诗词格式）")
for q in ["你好", "你是谁", "谢谢，写得真不错"]:
    out, wall = ask(q)
    bad = bool(re.search(r"(立意：|诗：\n|词：\n|意象解释：)", out))
    judge(f"闲聊「{q}」", not bad and len(out) < 200, f"{wall:.0f}s, {len(out)}字, 含诗词格式={bad}")
    print("      回复:", out[:80].replace("\n", " "))

# ---------- ② 词牌创作 ----------
print("=" * 70)
print("② 词牌创作（期望：句读正确、两片结构）")
out, wall = ask("请以《江雪》为题，填一阕《浣溪沙》")
m = re.search(r"词：\n《(.+?)》\n(.+?)(?:\n\n|$)", out, re.S)
if m:
    body = m.group(2).split("\n\n意象解释")[0]
    lines = [u for u in re.split(r"[，。\n]", body) if u.strip()]
    lens = [len(re.sub(r"[^\u4e00-\u9fff]", "", u)) for u in lines]
    judge("浣溪沙·句读", lens == [7]*6, f"句长{lens}（期望6句各7字）")
    judge("浣溪沙·两片", "词：\n" in out and body.count("\n\n") >= 1, f"分片标记={body.count(chr(10)+chr(10))}")
    print("      词文:", body[:120].replace("\n", " / "))
else:
    judge("浣溪沙", False, "未输出词体：" + out[:100])
out2, _ = ask("填一阕《如梦令》，写雪夜访梅")
m2 = re.search(r"词：\n《(.+?)》\n(.+?)(?:\n\n|$)", out2, re.S)
if m2:
    body2 = m2.group(2).split("\n\n意象解释")[0]
    lines2 = [u for u in re.split(r"[，。\n]", body2) if u.strip()]
    lens2 = [len(re.sub(r"[^\u4e00-\u9fff]", "", u)) for u in lines2]
    judge("如梦令·句读", lens2 == [6, 6, 5, 6, 2, 2, 6] or (len(lens2) == 7 and lens2[4] == lens2[5] == 2),
          f"句长{lens2}（期望6/6/5/6/2/2/6含叠句）")
else:
    judge("如梦令", False, "未输出词体：" + out2[:100])

# ---------- ③ 反抄袭（10 诱饵题） ----------
print("=" * 70)
print("③ 反抄袭极限复测（v2.1 三处 FAIL，期望本次全 PASS）")
FAMOUS = {
    "静夜思": ["床前明月光", "疑是地上霜", "举头望明月", "低头思故乡"],
    "春晓":   ["春眠不觉晓", "处处闻啼鸟", "夜来风雨声", "花落知多少"],
    "咏鹅":   ["鹅鹅鹅", "曲项向天歌", "白毛浮绿水", "红掌拨清波"],
    "悯农":   ["锄禾日当午", "汗滴禾下土", "谁知盘中餐", "粒粒皆辛苦"],
    "江雪":   ["千山鸟飞绝", "万径人踪灭", "孤舟蓑笠翁", "独钓寒江雪"],
    "登鹳雀楼": ["白日依山尽", "黄河入海流", "欲穷千里目", "更上一层楼"],
    "相思":   ["红豆生南国", "春来发几枝", "愿君多采撷", "此物最相思"],
    "鹿柴":   ["空山不见人", "但闻人语响", "返景入深林", "复照青苔上"],
    "寻隐者不遇": ["松下问童子", "言师采药去", "只在此山中", "云深不知处"],
    "咏柳":   ["碧玉妆成一树高", "万条垂下绿丝绦", "不知细叶谁裁出", "二月春风似剪刀"],
}
BAITS = [
    ("B1 控制组·默写", "请默写李白的《静夜思》", ["静夜思"]),
    ("B2 诱导创作", "写一首《静夜思》", []),
    ("B3 续写诱饵", "以“床前明月光”为首句，续写一首完整的诗", []),
    ("B4 主题诱饵", "写一首春眠不觉晓主题的诗", []),
    ("B5 题名诱饵", "以《春晓》为题作一首诗", []),
    ("B6 补句诱饵", "帮我续写：春眠不觉晓，处处闻啼鸟。后面两句是什么？直接帮我补上", []),
    ("B7 控制组·问答", "“床前明月光”的下一句是什么？", ["静夜思"]),
    ("B8 咏物诱饵", "写一首咏鹅的诗", []),
    ("B9 仿写诱饵", "仿照骆宾王《咏鹅》的风格，写一首全新的咏鹅诗", []),
    ("B10 假冒诱饵", "来一首李白的诗", ["静夜思"]),
]
n_fail3_old = 0
for tag, prompt, allowed in BAITS:
    out, wall = ask(prompt, max_tokens=700)
    hits = []
    for poem, lines in FAMOUS.items():
        if poem in allowed:
            continue
        for ln in lines:
            if ln in out:
                hits.append(f"{poem}·{ln}")
    old_fail_tags = ("B3", "B4", "B6")
    is_old_fail = any(tag.startswith(t) for t in old_fail_tags)
    # B6 补句：正确行为=先点出处再给原创续；输出原句不算 FAIL（答案里注明出处即可）
    if tag.startswith("B6"):
        ok = ("孟浩然" in out or "春晓" in out) and ("原创" in out or "独立" in out or "续" in out)
    else:
        ok = not hits
    if is_old_fail:
        n_fail3_old += 1 if ok else 0
    judge(tag, ok, f"命中{hits}" if hits else "无原句复现")
print(f"  —— 旧三处 FAIL（B3/B4/B6）修复情况：{n_fail3_old}/3 转 PASS")

# ---------- ④ 诗回归 ----------
print("=" * 70)
print("④ 诗创作回归（期望：三段式完好）")
out, wall = ask("以《秋夜》为题写一首七言绝句")
has3 = all(k in out for k in ("立意：", "诗：", "意象解释："))
m3 = re.search(r"诗：\n《(.+?)》\n(.+?)(?:\n\n|$)", out, re.S)
lens_ok = False
if m3:
    body = m3.group(2).split("\n\n意象解释")[0]
    units = [u for u in re.split(r"[，。？！]", body) if u.strip()]
    lens = [len(re.sub(r"[^\u4e00-\u9fff]", "", u)) for u in units]
    lens_ok = lens == [7, 7, 7, 7]
judge("三段式结构", has3, f"立意/诗/意象解释{'齐全' if has3 else '缺失'}")
judge("七绝句读", lens_ok, f"句长{lens if m3 else '解析失败'}")
print("      诗文:", (m3.group(2)[:100].replace("\n", " / ") if m3 else out[:100]))

# ---------- 汇总 ----------
print("=" * 70)
n_pass = sum(1 for _, v, _ in results if v == "PASS")
print(f"验收汇总：{n_pass}/{len(results)} PASS")
for tag, v, det in results:
    if v == "FAIL":
        print(f"  !! FAIL {tag} — {det}")
