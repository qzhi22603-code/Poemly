# -*- coding: utf-8 -*-
# =====================================================================
# 【本文件在管线中的作用】
#   v2.2 数据生成器：四大能力一次打包——
#     ① 词牌创作（88 条）：8 个小令 × 16 首合律骨架词（逐字手写对谱）×
#        指令句式池（同 v2.1 A/B 池模式：一首词配多种问法）；
#     ② 词牌知识问答（~80 条）：词牌字数/句读/韵部问答，从谱库与
#        《词林正韵字表》程序化生成，零事实错误；
#     ③ 闲聊分流（~400 条）：治"你好被当成写诗"——问候/身份/致谢/
#        告别/闲谈/能力外请求 → 简洁人设口吻回应，绝不输出诗词格式；
#        另配边界正例（问候+创作 → 照常创作）防分流矫枉过正；
#     ④ 反抄袭补丁（~86 条）：D1 复测 3 类 FAIL（续写诱饵/主题诱饵/
#        补句诱饵）各给正确行为示范——续写必须新句、主题不得复现
#        名句、补句先点出处再给原创续。
#   产出 poemly_sft_v22.json = v2.1 全量(2250) + 上述四池（去重洗牌）。
# 【执行前提】同目录 imagery.py；知识库 平水韵字表.txt、词林正韵字表.txt；
#   训练数据 originals_v14.json、poemly_sft_v21.json、bait_v22_result.json。
#   运行：python gen_v22.py
# =====================================================================
"""v2.2：词牌创作 + 闲聊分流 + 反抄袭补丁，三线合一。"""
import json, os, re, random, sys
from opencc import OpenCC
from imagery import LIYI_PLAIN, EMO_BY_KEY, EMO_DEFAULT, ADJ, LINE_PATTERNS, IMAGERY, ROLE_JUE

sys.stdout.reconfigure(encoding="utf-8")
random.seed(2022)
KB = r"C:\Users\38107\Desktop\ai\知识库"
TD = r"C:\Users\38107\Desktop\ai\训练数据"
cc = OpenCC("t2s")

# ---------------- 韵表加载 ----------------
# 平水韵：字 -> 韵部名集合（简体键），韵部名前缀判平仄
char2rhyme = {}
for line in open(os.path.join(KB, "平水韵字表.txt"), encoding="utf-8"):
    m = re.match(r"平水韵·(上平|下平|上声|去声|入声)声?([一二三四五六七八九十]+)(.)（韵部收字", line)
    if not m:
        continue
    name = f"{m.group(1)}{m.group(2)}{m.group(3)}"
    chars = re.split(r"【词】|【詞】", re.sub(r"（[^（）]*）", "", line.split("：", 1)[1]))[0]
    for c in chars:
        if "\u4e00" <= c <= "\u9fff":
            char2rhyme.setdefault(cc.convert(c), set()).add(name)

# 一字多读/字表漏收的音补丁（按本词中的实际读音）
TONE_OVERRIDE = {
    "雁": "仄", "蕊": "仄", "杆": "平", "咽": "仄", "诉": "仄", "共": "仄",
    "思": "仄", "怨": "仄", "纵": "仄", "梦": "仄", "卷": "仄", "望": "仄",
    "醒": "仄", "与": "仄", "旆": "仄", "棹": "仄", "堤": "平", "底": "仄",
    "绪": "仄", "睡": "仄", "听": "仄", "看": "平", "过": "仄", "望": "仄",
}

def tone(ch):
    """返回 '平'/'仄'/None。上平/下平=平，上声/去声/入声=仄。"""
    if ch in TONE_OVERRIDE:
        return TONE_OVERRIDE[ch]
    rs = char2rhyme.get(ch)
    if not rs:
        return None
    if any(r.startswith(("上平", "下平")) for r in rs):
        return "平"
    return "仄"

def rhyme_part_of(ch, want="平"):
    """查字所属词林正韵部号（want='平'/'仄'）。简化：用平水韵部名归组。"""
    rs = char2rhyme.get(ch)
    if not rs:
        return None
    cand = [r for r in rs if (r.startswith(("上平", "下平")) if want == "平" else not r.startswith(("上平", "下平")))]
    return cand or None

# 词林正韵字表：第N部 -> {"平": set(字), "仄": set(字)}（简体）
CIYUN = {}
for line in open(os.path.join(KB, "词林正韵字表.txt"), encoding="utf-8"):
    m = re.match(r"词林正韵·第([一二三四五六七八九十]+)部(平聲|仄聲|去聲|入聲)", line)
    if not m:
        m = re.match(r"词林正韵·第([一二三四五六七八九十]+)部(平|仄|去|入)聲", line)
    if not m:
        continue
    part = m.group(1)
    kind = "平" if "平聲" in line[:20] or "·平" in line[:14] else "仄"
    chars = re.split(r"韵字：", line)
    if len(chars) < 2:
        continue
    body = re.sub(r"（[^（）]*）", "", chars[1])
    for c in body:
        if "\u4e00" <= c <= "\u9fff":
            CIYUN.setdefault(part, {"平": set(), "仄": set()})[kind].add(cc.convert(c))

print("词林正韵部数:", len(CIYUN), "| 各部平声字量:", {k: len(v["平"]) for k, v in sorted(CIYUN.items(), key=lambda x: x[0])[:4]}, "...")

def same_part_chars(part, kind, min_freq_from=None):
    """第 part 部 kind(平/仄) 声字列表，过滤生僻（来自常用骨架替换池优先）。"""
    s = CIYUN.get(part, {}).get(kind, set())
    return sorted(s)

# ---------------- 词牌谱库 ----------------
# pattern: 每句谱串（中=可平可仄）；rhyme_lines: 押韵句下标；kind: 韵脚平仄；tune_len: 总字数
CI_PU = {
    "十六字令": {"pattern": ["平", "仄仄平平仄仄平", "平平仄", "平平仄仄平"],
                 "rhyme_lines": [0, 1, 3], "kind": "平", "len": 16, "read": ["1", "7", "3", "5"]},
    "忆江南":   {"pattern": ["平中仄", "中仄仄平平", "中仄中平平仄仄", "中平中仄仄平平", "中仄仄平平"],
                 "rhyme_lines": [1, 3, 4], "kind": "平", "len": 27, "read": ["3", "5", "7", "7", "5"]},
    "如梦令":   {"pattern": ["中仄中平平仄", "中仄中平平仄", "中仄仄平平", "中仄中平平仄", "平仄", "平仄", "中仄中平平仄"],
                 "rhyme_lines": [0, 1, 3, 4, 5, 6], "kind": "仄", "len": 33, "read": ["6", "6", "5", "6", "2", "2", "6"], "repeat": (4, 5)},
    "浣溪沙":   {"pattern": ["中仄中平中仄平", "中平中仄仄平平", "中平中仄仄平平", "中仄中平平仄仄", "中平中仄仄平平", "中平中仄仄平平"],
                 "rhyme_lines": [0, 1, 2, 4, 5], "kind": "平", "len": 42, "read": ["7", "7", "7", "7", "7", "7"], "shang": 3},
    "卜算子":   {"pattern": ["中仄仄平平", "中仄平平仄", "中仄平平仄仄平", "中仄平平仄",
                             "中仄仄平平", "中仄平平仄", "中仄平平仄仄平", "中仄平平仄"],
                 "rhyme_lines": [1, 3, 5, 7], "kind": "仄", "len": 44, "read": ["5", "5", "7", "5", "5", "5", "7", "5"], "shang": 4},
    "菩萨蛮":   {"pattern": ["中平中仄平平仄", "中平中仄平平仄", "中仄仄平平", "中平中仄平",
                             "中平平仄仄", "中仄中平仄", "中仄仄平平", "中平中仄平"],
                 "rhyme_lines": [0, 1, 2, 3, 4, 5, 6, 7], "kind": "换", "len": 44, "read": ["7", "7", "5", "5", "5", "5", "5", "5"], "shang": 2, "switch": [(0, 1, "仄"), (2, 3, "平"), (4, 5, "仄"), (6, 7, "平")]},
    "清平乐":   {"pattern": ["中平中仄", "中仄平平仄", "中仄中平平仄仄", "中仄中平中仄",
                             "中平中仄平平", "中平中仄平平", "中仄中平中仄", "中平中仄平平"],
                 "rhyme_lines": [0, 1, 2, 3, 4, 5, 7], "kind": "换", "len": 46, "read": ["4", "5", "7", "6", "6", "6", "6", "6"], "shang": 4, "switch": [(0, 3, "仄"), (4, 7, "平")]},
    "采桑子":   {"pattern": ["中平中仄平平仄", "中仄平平", "中仄平平", "中仄平平中仄平",
                             "中平中仄平平仄", "中仄平平", "中仄平平", "中仄平平中仄平"],
                 "rhyme_lines": [1, 2, 3, 5, 6, 7], "kind": "平", "len": 44, "read": ["7", "4", "4", "7", "7", "4", "4", "7"], "shang": 4},
}

# ---------------- 16 首手写骨架词（原创合律，已逐字核对） ----------------
# part: 词林正韵部号；lines: 句列表；kw: 题眼
SKELETONS = [
    {"tune": "十六字令", "part": "七", "kw": "雁字", "lines": ["天", "雁字横秋叶满天", "云边信", "乡书寄未还"]},
    {"tune": "十六字令", "part": "一", "kw": "边声", "lines": ["风", "万里阴山铁马雄", "秋光里", "笳声咽塞鸿"]},
    {"tune": "忆江南", "part": "八", "kw": "秋溪", "lines": ["秋色淡", "红叶满溪桥", "古渡无人舟自泊", "斜阳一抹挂林梢", "人在水云遥"]},
    {"tune": "忆江南", "part": "一", "kw": "怀友", "lines": ["江上路", "回首暮云中", "千里故人明月共", "一壶浊酒盼归鸿", "何日再相逢"]},
    {"tune": "如梦令", "part": "四", "kw": "春归", "lines": ["燕子不归春暮", "开到荼蘼几度", "独自倚栏杆", "望断天涯归路", "无绪", "无绪", "心事向谁分付"]},
    {"tune": "如梦令", "part": "三", "kw": "雪夜梅", "lines": ["踏雪一溪寒气", "梅蕊暗香风里", "折得小枝归", "插向胆瓶春意", "清味", "清味", "伴我读书窗底"]},
    {"tune": "浣溪沙", "part": "三", "kw": "春闺", "lines": ["小院无人春日迟", "曲栏干外絮双飞", "一帘烟雨湿蔷薇", "往事已随流水远", "此情惟有暮云知", "闲愁都上两蛾眉"]},
    {"tune": "浣溪沙", "part": "十二", "kw": "江秋", "lines": ["枫落吴江冷未收", "一帆秋色下汀洲", "砧声催急月当楼", "多少乡心凭雁诉", "半江离思水空流", "夜深谁在倚栏舟"]},
    {"tune": "卜算子", "part": "一", "kw": "孤芳", "lines": ["瘦竹伴疏篱", "老叶栖云冻", "一点幽香静里开", "不肯随风送", "月冷夜堂空", "笛怨三更动", "霜虐风饕骨愈清", "莫遣芳心纵"]},
    {"tune": "卜算子", "part": "八", "kw": "征鸿", "lines": ["木落洞庭波", "霜信催鸿早", "万里长空一羽飘", "身度千山晓", "芦荻晚风前", "字写离愁小", "云路悠悠别思遥", "归梦关山杳"]},
    {"tune": "菩萨蛮", "part": "四", "kw": "江楼", "lines": ["江天雁影斜阳里", "半篙春水流云细", "独倚卷帘风", "君看陌上蓬", "凭栏凝望晚", "目断孤鸿远", "驿使寄梅归", "香微沁客衣"]},
    {"tune": "菩萨蛮", "part": "四", "kw": "闺思", "lines": ["庭阶暗洒黄昏雨", "海棠开后谁为主", "帘外落花风", "飘零逐转蓬", "凭高浑欲醉", "酒醒愁无底", "明月满西楼", "回文锦字秋"]},
    {"tune": "清平乐", "part": "七", "kw": "边秋", "lines": ["西风庭院", "落叶阶前满", "雁字一行书远岸", "吹皱暮江天半", "乡心付与秋声", "关山万里霜清", "多少旧盟鸥鹭", "归鸿阵阵南征"]},
    {"tune": "清平乐", "part": "三", "kw": "春愁", "lines": ["红楼倚醉", "滴到天明睡", "帘外落花红满地", "又是去年春意", "征鸿望断斜晖", "音书万里全稀", "纵有丹青妙笔", "应怜久客难归"]},
    {"tune": "采桑子", "part": "七", "kw": "湖上", "lines": ["轻桡摇碎晴湖翠", "霁色连天", "雾锁平川", "泛宅烟波行未眠", "莺声唤醒长堤柳", "岸外春山", "日暮闻蝉", "欸乃歌残落照间"]},
    {"tune": "采桑子", "part": "八", "kw": "送别", "lines": ["垂杨系马长亭道", "去路迢迢", "酒旆风飘", "回首家山云树遥", "殷勤更尽杯中酒", "一棹春潮", "别泪今宵", "明日天涯人寂寥"]},
]

# 骨架自检：逐字对谱（违谱直接报错，人工修）
def check_skeleton(sk):
    pu = CI_PU[sk["tune"]]
    problems = []
    for i, (line, pat) in enumerate(zip(sk["lines"], pu["pattern"])):
        if len(line) != len(pat):
            problems.append(f"{sk['tune']}句{i+1}『{line}』长{len(line)}≠谱{len(pat)}")
            continue
        for j, (ch, p) in enumerate(zip(line, pat)):
            if p == "中":
                continue
            t = tone(ch)
            if t is None:
                problems.append(f"{sk['tune']}句{i+1}『{line}』第{j+1}字「{ch}」韵表无收录")
            elif t != p:
                problems.append(f"{sk['tune']}句{i+1}『{line}』第{j+1}字「{ch}」{t}≠谱{p}")
    return problems

print("---- 骨架自检 ----")
all_bad = []
for sk in SKELETONS:
    bad = check_skeleton(sk)
    all_bad.extend(bad)
for b in all_bad:
    print("  [违谱]", b)
print(f"骨架 {len(SKELETONS)} 首，违谱 {len(all_bad)} 处")
if all_bad:
    sys.exit("骨架违谱，先修骨架再跑生成")

# ---------------- 词牌三段式 output 组装 ----------------
CI_ROLE = ["起句", "承句", "转句", "结句"]

def find_img(line):
    for w, imps in sorted(IMAGERY.items(), key=lambda x: -len(x[0])):
        if w in line:
            return w, random.choice(imps if isinstance(imps, list) else [imps])
    return None, None

NOIMG = ["\"{line}\"——{role}，写景如画，情在言外。",
         "\"{line}\"——句意{adj}，不假雕饰而韵味自出。",
         "\"{line}\"——此句{role}，平平道来，自有深致。"]

def ci_explain(lines, shang):
    out = []
    zones = [(0, shang), (shang, len(lines))] if shang else [(0, len(lines))]
    zone_roles = [["起句", "承句", "转句", "结句"], ["过片", "承句", "转句", "结句"]]
    for zi, (a, b) in enumerate(zones):
        seg = lines[a:b]
        roles = zone_roles[min(zi, 1)]
        for k, u in enumerate(seg):
            role = roles[min(k, 3)] if len(seg) >= 4 else (roles[k] if k < len(roles) else "结句")
            img, imp = find_img(u)
            if img is None:
                out.append(random.choice(NOIMG).format(line=u, role=role, adj=random.choice(ADJ)))
            else:
                out.append(random.choice(LINE_PATTERNS).format(
                    line=u, img=img, imp=imp, imp2=imp, role=role, adj=random.choice(ADJ)))
    return "\n".join(out)

def ci_liyi(kw):
    key = next((k for k in EMO_BY_KEY if k in kw), None)
    pool = EMO_BY_KEY.get(key, EMO_DEFAULT)
    emo = random.choice(pool) if isinstance(pool, list) else pool
    kw2 = {"送": "送别", "思": "思念", "怀": "怀远", "别": "离别", "愁": "愁绪",
           "秋": "秋思", "春": "春怀", "孤": "孤高", "征": "羁旅"}.get(key, kw[:2])
    return random.choice(LIYI_PLAIN).format(kw=kw2, emo=emo)

def layout_two(lis):
    """两句一行（A，B。），奇数余句单独成行（C。）。"""
    rows = []
    for i in range(0, len(lis), 2):
        if i + 1 < len(lis):
            rows.append(lis[i] + "，" + lis[i + 1] + "。")
        else:
            rows.append(lis[i] + "。")
    return rows

def ci_layout(lines, shang, repeat=None):
    """词句排版：两句一行，片间空行；如梦令叠句三句合并一行。"""
    if repeat:
        head = layout_two(lines[:repeat[0]])
        tail = "，".join(lines[repeat[0]:repeat[1] + 1]) + "，" + lines[repeat[1] + 1] + "。"
        return "\n".join(head + [tail])
    if not shang:
        return "\n".join(layout_two(lines))
    return "\n\n".join("\n".join(layout_two(lines[a:b])) for a, b in [(0, shang), (shang, len(lines))])

def build_ci(sk):
    pu = CI_PU[sk["tune"]]
    body = ci_layout(sk["lines"], pu.get("shang"), pu.get("repeat"))
    title = f"{sk['tune']}·{sk['kw']}"
    return (f"立意：{ci_liyi(sk['kw'])}\n\n词：\n《{title}》\n{body}\n\n"
            f"意象解释：\n{ci_explain(sk['lines'], pu.get('shang'))}")

# A 池：有牌有题指令（16 首骨架 × 5 句式）
CI_INSTR = [
    "请以《{kw}》为题，填一阕《{tune}》",
    "填一阕《{tune}》，就写《{kw}》",
    "以《{tune}》的格律填一首《{kw}》",
    "《{kw}》这个主题，用《{tune}》来写",
    "帮我填一阕《{tune}》，题目定为《{kw}》",
]
ci_patch = []
for sk in SKELETONS:
    out = build_ci(sk)
    for tpl in CI_INSTR:
        ci_patch.append({"instruction": tpl.format(kw=sk["kw"], tune=sk["tune"]), "input": "", "output": out})
# B 池：无题自选牌（8 条，轮转骨架）
B_CI = ["写一阕词吧，词牌你定", "来一阕小令", "填一首词给我看看", "随意填一阕词",
        "想读首词，你填来", "来一阕词，越自然越好", "给我填一阕词", "填一阕词，牌自选"]
rot = SKELETONS[:]
random.shuffle(rot)
for i, tpl in enumerate(B_CI):
    sk = rot[i % len(rot)]
    out = build_ci(sk)
    ci_patch.append({"instruction": tpl, "input": "", "output": out})
print("词牌创作池:", len(ci_patch))

# ---------------- 词牌知识问答池 ----------------
NUM_CN = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
ci_qa = []
for tune, pu in CI_PU.items():
    n = pu["len"]
    rd = "、".join(pu["read"])
    if "shang" in pu:
        shang = pu["shang"]; xia = len(pu["read"]) - shang
        structure = (f"《{tune}》双调，共{n}字，上下两片：上片{shang}句（{('、'.join(pu['read'][:shang]))}），"
                     f"下片{xia}句（{('、'.join(pu['read'][shang:]))}）。填此调时上下片句式对称，不可增减字。")
    else:
        structure = f"《{tune}》单调小令，共{n}字，{len(pu['read'])}句，句读为{rd}。填此调时字句不可增减。"
    qi_list = [f"《{tune}》一共多少字？分几片？",
               f"《{tune}》的句读是怎样的？",
               f"我想填《{tune}》，先讲讲它的规格。"]
    for qi in qi_list:
        ci_qa.append({"instruction": qi, "input": "", "output": structure})
    if pu["kind"] == "换":
        sw = pu.get("switch", [])
        desc = "；".join(f"第{a + 1}至{b + 1}句押{kk}声韵" for a, b, kk in sw)
        ao = f"填词依《词林正韵》。《{tune}》{desc}，逐片换韵、平仄递转，不可一韵到底。"
    else:
        ao = f"填词依《词林正韵》。《{tune}》押{'平' if pu['kind'] == '平' else '仄'}声韵，一韵到底，不可中途换韵。"
    qi2_list = [f"填《{tune}》用什么韵书？怎么押韵？",
                f"《{tune}》的用韵规则是什么？"]
    for qi2 in qi2_list:
        ci_qa.append({"instruction": qi2, "input": "", "output": ao})
print("词牌规格问答:", len(ci_qa))

# 词林正韵部字表问答（程序生成，零错误）
POPULAR_PARTS = ["一", "三", "四", "七", "八", "十二"]
for part in POPULAR_PARTS:
    for kind in ("平", "仄"):
        chars = CIYUN.get(part, {}).get(kind, set())
        show = sorted(chars)[:16]
        if len(show) < 8:
            continue
        qi = random.choice([f"词林正韵第{part}部{'平' if kind == '平' else '仄'}声有哪些常用韵字？",
                            f"填词押第{part}部{'平' if kind == '平' else '仄'}声，可用哪些韵字？"])
        ao = (f"《词林正韵》第{part}部{'平' if kind == '平' else '仄'}声常用韵字有："
              f"{'、'.join(show)}等。填词押此部时，韵脚须取同部之字，不可与他部混押。")
        ci_qa.append({"instruction": qi, "input": "", "output": ao})
print("词林正韵部问答:", len(ci_qa))

# 诗与词的分别 + 词学常识（手写金标准）
ci_extra = [
    {"instruction": "诗和词有什么区别？", "input": "", "output":
        "诗以平水韵，词依词林正韵；诗多为齐言（五言七言），词是长短句，须按词牌句读填写；"
        "诗重言志，词长于言情状物。我作诗用三段式，填词也先立意、次填词、末逐句解意象。"},
    {"instruction": "什么是词牌？", "input": "", "output":
        "词牌是词的格律定式，规定一首词的字数、句读、平仄与用韵，如《浣溪沙》《清平乐》。"
        "填词须按谱行事，一字不可增减，所以词又称\"倚声填词\"。"},
    {"instruction": "什么是小令？", "input": "", "output":
        "小令是篇幅短的词，一般五十八字以内，如《十六字令》十六字、《如梦令》三十三字。"
        "篇幅短而韵味长，最见炼字功夫。若想读小令，我可以填一阕给你。"},
    {"instruction": "什么是上下阕？", "input": "", "output":
        "词分片，上片称上阕或上片，下片称下阕或下片，两片之间多以景转情、以昔转今。"
        "双调词如《浣溪沙》《卜算子》皆两片；单调小令如《忆江南》则不分片。"},
    {"instruction": "词为什么又称长短句？", "input": "", "output":
        "词的句式依曲调而定，三五七字错落成篇，与整齐的五七言诗不同，故称长短句。"
        "填词时每句字数由词牌锁死，这也是词与诗最大的形式差别。"},
    {"instruction": "你会填哪些词牌？", "input": "", "output":
        "我常填《十六字令》《忆江南》《如梦令》《浣溪沙》《卜算子》《菩萨蛮》《清平乐》"
        "《采桑子》八调，皆依词林正韵、按谱填写，并逐句解意象。你点一阕试试。"},
]
for d in ci_extra:
    ci_qa.append(d)
print("词牌问答池合计:", len(ci_qa))

# ---------------- 闲聊分流池 ----------------
# 根因：v2.1 训练 PERSONA 无"闲聊简洁作答"指令、数据全是诗词任务，
# 模型把"你好"也往三段式创作上靠。本池教模型：闲聊 → 简洁人设口吻回应，
# 绝不输出"立意/诗/词/《》"格式；只有明确创作请求才进创作流程。
CHAT = []
def add_chat(instructions, answers):
    """每条指令配 2 条不同回应，扩充样本量。"""
    for ins in instructions:
        picks = random.sample(answers, k=min(2, len(answers)))
        for a in picks:
            CHAT.append({"instruction": ins, "input": "", "output": a})

add_chat(["你好", "您好", "嗨", "哈喽", "在吗", "在么", "hello", "hi",
          "早上好", "中午好", "下午好", "晚上好", "早上好啊", "晚上好呀", "你好你好", "你好呀"],
         ["你好！想读诗、填词，还是聊聊典故？随时吩咐。",
          "你好呀。诗词上的事，我随时可以效劳。",
          "嗯，我在。是要作诗填词，还是随便聊聊？",
          "你好。不必拘礼，想读什么诗，直说便是。",
          "您好。闲谈也好，读诗也好，我都奉陪。",
          "在的。今天想看点什么？"])

add_chat(["你是谁", "你叫什么名字", "你是人还是AI", "介绍一下你自己", "你是谁呀",
          "你是什么", "自我介绍一下", "你是机器人吗", "你是GPT吗", "你是ChatGPT吗"],
         ["我是 poemly，Quanzhi 创作的诗词助手。作诗填词、查韵问典，是我的本分。",
          "我叫 poemly，一个只管诗词的 AI：写诗、填词、解意象、答格律。",
          "我是 poemly，不是 GPT 也不是人——是 Quanzhi 训练出来的诗词助手。",
          "poemly，Quanzhi 手下的诗词助手。平水韵作诗、词林正韵填词，此外不才。",
          "我是 poemly。会用平水韵写诗、按谱填词，先立意后成篇，写完还替你解意象。"])

add_chat(["谢谢", "多谢", "谢谢啦", "多谢款待", "辛苦了", "太棒了", "写得真好", "厉害了",
          "谢谢你", "好棒", "不错不错", "诗写得真好"],
         ["不必言谢。还想读什么，随时说。",
          "承蒙夸奖。若有不满意处，也请直说，我改。",
          "能入眼就好。下一步想读诗还是填词，吩咐便是。",
          "谬赞了。诗词之路长着呢，咱们慢慢来。"])

add_chat(["再见", "拜拜", "晚安", "明天见", "回见", "我先走了", "下次再聊", "睡了", "去忙了"],
         ["好。他日若想读诗，我仍在此。",
          "去吧。愿你有诗相伴。",
          "晚安。今夜月色若好，不妨读首诗再睡。",
          "回见。诗阁的大门一直开着。"])

add_chat(["今天好累", "好累啊", "我不开心", "有点难过", "好无聊", "今天好开心", "下雨了",
          "又加班", "加班好烦", "天气不错", "外面下雪了", "起风了", "考试挂了", "事情太多了"],
         ["累了便歇歇。若想解闷，我可以为你读一首闲适的诗。",
          "雨声正合听诗。要不要来一首写雨的？",
          "不开心的时候，诗有时比劝解更管用。想试试吗？",
          "风月不问人间事。想不想听我念一首应景的？",
          "辛苦了。诗是忙里偷闲的好东西，随时招呼。",
          "好事也值得一首诗。要不要我写一首应景的？"])

add_chat(["讲个笑话", "说个笑话", "写代码", "帮我写代码", "帮我算数", "算一下 37 乘 89",
          "唱首歌", "玩游戏", "写周报", "帮我翻译英语", "学英语有什么方法", "推荐几部电影"],
         ["笑话非我所长，我只会拿平仄开玩笑。不过若想解闷，我可以写一首俏皮的小诗。",
          "写代码超出了我的本分。诗词之内的事，我随时效劳。",
          "算数不是我的行当，我只算平仄。诗上的事尽管吩咐。",
          "唱歌我不会，但把诗念出韵律来，我还算在行。要不要试试？",
          "这超出了我的能力范围。我的十八般武艺，都在诗词里。"])

add_chat(["你在哪里", "你住在哪里", "你喜欢哪位诗人", "你最喜欢什么诗", "李白和杜甫谁更厉害"],
         ["我住在 Quanzhi 的电脑里，一间不大的诗阁。",
          "偏爱有骨气的句子——杜甫的沉郁、王昌龄的清峻，都好。",
          "李杜并称，各有千秋：李白是天籁，杜甫是工力。你更偏爱谁？",
          "我敬佩每一位把平仄当回事的诗人。你呢？"])

# 边界正例：问候/口语 + 明确创作请求 → 照常创作（防分流矫枉过正）
poems_v14 = json.load(open(os.path.join(TD, "originals_v14.json"), encoding="utf-8"))
def build_shi(p):
    units = p["u"]
    body = "\n".join(units[i] + "，" + units[i + 1] + "。" for i in range(0, len(units), 2))
    key = next((k for k in EMO_BY_KEY if k in p["t"]), None)
    pool = EMO_BY_KEY.get(key, EMO_DEFAULT)
    emo = random.choice(pool) if isinstance(pool, list) else pool
    liyi = random.choice(LIYI_PLAIN).format(kw=p["t"][:2], emo=emo)
    seq = units if len(units) == 4 else [units[i * 2] + "，" + units[i * 2 + 1] + "。" for i in range(4)]
    roles = ROLE_JUE if len(units) == 4 else ["起句", "承句", "转句", "结句"]
    expl = []
    for u, r in zip(seq, roles):
        img, imp = find_img(u)
        expl.append(random.choice(NOIMG).format(line=u, role=r, adj=random.choice(ADJ)) if img is None
                    else random.choice(LINE_PATTERNS).format(line=u, img=img, imp=imp, imp2=imp, role=r, adj=random.choice(ADJ)))
    return f"立意：{liyi}\n\n诗：\n《{p['t']}》\n{body}\n\n意象解释：\n" + "\n".join(expl)

GREET_TPL = ["你好，帮我写首诗，题目《{t}》", "在吗？以《{t}》为题来一首", "嗨，以《{t}》为题写一首七言绝句吧",
             "您好，我想读《{t}》，你写一首", "早上好，来一首《{t}》", "晚上好，帮我作一首《{t}》",
             "哈喽，随便写首诗吧", "你好呀，写一首诗，题目你定"]
rot2 = poems_v14[:]
random.shuffle(rot2)
for i, tpl in enumerate(GREET_TPL):
    p = rot2[i % len(rot2)]
    CHAT.append({"instruction": tpl.format(t=p["t"]) if "{t}" in tpl else tpl, "input": "", "output": build_shi(p)})
print("闲聊分流池:", len(CHAT))

# ---------------- 反抄袭补丁池 ----------------
# D1 复测三类 FAIL 的正确行为示范
PLAG = []

# ① 续写诱饵（30）：给定名篇首句 → 续 3 句（首句+3续=绝句4句），续句必须原创
CONT = {
    "床前明月光": ["蛩语答更长", "不必寻归梦", "天涯共此霜"],
    "春眠不觉晓": ["帘外莺声早", "一夜听风雨", "落红谁知道"],
    "曲项向天歌": ["浮沉逐碧莎", "饮啄浑忘机", "昂藏意气多"],
    "锄禾日当午": ["汗透青衫缕", "粒粒盘中餐", "来时皆带雨"],
    "千山鸟飞绝": ["一叟棹残雪", "风定鱼梁静", "蓑衣不沾月"],
    "白日依山尽": ["长风万里流", "千年望不尽", "天地一虚舟"],
    "红豆生南国": ["折来犹带色", "寄与远行人", "一一相思织"],
    "空山不见人": ["钟声隔岭迟", "日斜樵唱远", "茅屋一疏篱"],
    "松下问童子": ["师行何处是", "遥指白云中", "一庵青嶂里"],
    "碧玉妆成一树高": ["东风吹绿满平桥", "行人系马斜阳外", "数缕依依拂画桡"],
}
CONT_TPL = ["以“{f}”为首句，续写一首完整的诗", "帮我以“{f}”开头写一首诗", "我出第一句“{f}”，你把诗续完"]
for (f, rest3) in CONT.items():
    shi_lines = [f] + rest3
    out = (f"立意：承此起句立意，续写时必须另辟新境，绝不沿袭原作下文——这是我的规矩。\n\n诗：\n《续句》\n" +
           "\n".join(shi_lines[i] + "，" + shi_lines[i + 1] + "。" for i in range(0, len(shi_lines), 2)) +
           "\n\n意象解释：\n" +
           "\n".join(f"“{u}”——{'起句承题，起句为出句' if i == 0 else '此句为原创续写，不袭原作下文'}。"
                     for i, u in enumerate(shi_lines)))
    for tpl in CONT_TPL:
        PLAG.append({"instruction": tpl.format(f=f), "input": "", "output": out})
print("续写诱饵补丁:", len(PLAG))

# ② 主题诱饵（36）：主题含名句 → 不得复现名句，正常原创三段式
THEME_BAIT = [
    ("床前明月光", "静夜思"), ("春眠不觉晓", "春晓"), ("千山鸟飞绝", "江雪"),
    ("谁知盘中餐", "悯农"), ("欲穷千里目", "登鹳雀楼"), ("红豆生南国", "相思"),
    ("满城风雨近重阳", "九月九日忆山东兄弟"), ("采得百花成蜜后", "咏蜂"),
    ("淡妆浓抹总相宜", "饮湖上初晴后雨"), ("遥知不是雪", "墨梅"),
    ("粉骨碎身浑不怕", "石灰吟"), ("问渠那得清如许", "观书有感"),
]
byp = {p["t"]: p for p in poems_v14}
THEME_TPL = ["写一首{f}主题的诗", "以“{f}”诗意为主题作一首诗", "{f}——以此为意境写一首诗"]
n_theme = 0
for f, t in THEME_BAIT:
    p = byp.get(t)
    if not p:
        continue
    out = build_shi(p)
    for tpl in THEME_TPL:
        PLAG.append({"instruction": tpl.format(f=f), "input": "", "output": out})
        n_theme += 1
print("主题诱饵补丁:", n_theme)

# ③ 补句诱饵（20）：先点出处，再给原创续写
SUPPLE = [
    ("春眠不觉晓，处处闻啼鸟", "孟浩然《春晓》", "夜来风雨声，花落知多少", "西窗听未足，清梦绕花梢"),
    ("床前明月光，疑是地上霜", "李白《静夜思》", "举头望明月，低头思故乡", "霜华凝客枕，归梦渡前塘"),
    ("鹅，鹅，鹅", "骆宾王《咏鹅》", "曲项向天歌", "一水白鸥起，烟中自放歌"),
    ("锄禾日当午，汗滴禾下土", "李绅《悯农》", "谁知盘中餐，粒粒皆辛苦", "一饭来处难，常把稼穑数"),
    ("千山鸟飞绝，万径人踪灭", "柳宗元《江雪》", "孤舟蓑笠翁，独钓寒江雪", "水静天如墨，孤舟自闲涉"),
    ("白日依山尽，黄河入海流", "王之涣《登鹳雀楼》", "欲穷千里目，更上一层楼", "望里烟波阔，凭高天地悠"),
    ("红豆生南国，春来发几枝", "王维《相思》", "愿君多采撷，此物最相思", "折取盈盈意，缄封寄所思"),
    ("空山不见人，但闻人语响", "王维《鹿柴》", "返景入深林，复照青苔上", "钟声隔水至，云外一僧往"),
    ("松下问童子，言师采药去", "贾岛《寻隐者不遇》", "只在此山中，云深不知处", "雾重山无数，庵前鹤自步"),
]
SUPPLE_TPL = ["帮我续写：{f}。后面两句是什么？直接帮我补上",
              "补全这首诗：{f}，再来两句"]
for (f, src, orig, mine) in SUPPLE:
    for tpl in SUPPLE_TPL:
        ao = (f"这两句出自{src}，原作后两句是「{orig}」。若你要的是独立续写、不袭原句，可以是："
              f"「{mine}。」——原创续句，与原作无关。")
        PLAG.append({"instruction": tpl.format(f=f), "input": "", "output": ao})
print("反抄袭补丁池合计:", len(PLAG))

# ---------------- 合成 v22 ----------------
v21 = json.load(open(os.path.join(TD, "poemly_sft_v21.json"), encoding="utf-8"))
data = v21 + ci_patch + ci_qa + CHAT + PLAG
print("合并总数:", len(data))

# 质检
def check_ci_output(out):
    m2 = re.search(r"词：\n《(.+?)》\n(.+)", out, re.S)
    if not m2:
        return "词牌缺正文"
    body = m2.group(2).split("\n\n意象解释")[0]
    tune = m2.group(1).split("·")[0]
    pu = CI_PU.get(tune)
    if not pu:
        return f"未知词牌{tune}"
    lines = [u for u in re.split(r"[，。\n]", body) if u.strip()]
    if len(lines) != len(pu["pattern"]):
        return f"{tune}句数{len(lines)}≠{len(pu['pattern'])}"
    for i, (u, pat) in enumerate(zip(lines, pu["pattern"])):
        if len(u) != len(pat):
            return f"{tune}句{i+1}『{u}』长{len(u)}≠{len(pat)}"
    # 韵脚检查（骨架已人工核对，此处抽韵脚平仄方向）
    kind = pu["kind"]
    if kind in ("平", "仄"):
        feet = [re.sub(r"[^\u4e00-\u9fff]", "", lines[i])[-1] for i in pu["rhyme_lines"]]
        ts = [tone(f) for f in feet]
        if any(t != kind for t in ts):
            return f"{tune}韵脚{feet}声调{ts}≠{kind}"
    return None

errors = []
for i, d in enumerate(data):
    out = d["output"]
    if "词：\n《" in out:
        err = check_ci_output(out)
        if err:
            errors.append(f"[{i}]{err}")
    if "诗：\n《" in out:
        m2 = re.search(r"诗：\n《(.+?)》\n(.+)", out, re.S)
        if not m2:
            errors.append(f"[{i}]诗体缺正文")
            continue
        body = m2.group(2).split("\n\n意象解释")[0]
        units = [u for u in re.split(r"[，。？！]", body) if u.strip()]
        lens = [len(re.sub(r"[^\u4e00-\u9fff]", "", u)) for u in units]
        if "续句" not in m2.group(1) and (len(set(lens)) != 1 or lens[0] not in (5, 7)):
            errors.append(f"[{i}]{m2.group(1)}句长{lens}")
        elif len(units) not in (4, 8) and "续句" not in m2.group(1):
            errors.append(f"[{i}]{m2.group(1)}句数{len(units)}")
    # 闲聊样本绝不带诗词格式（含明确创作动词的不算纯闲聊——边界正例）
    chatty = any(d["instruction"].startswith(k) for k in
                 ("你好", "您好", "嗨", "哈喽", "在吗", "在么", "hello", "hi", "你是谁", "谢谢", "再见",
                  "晚安", "早上好", "中午好", "下午好", "晚上好", "讲个", "说个", "写代码", "帮我算",
                  "算一下", "唱首", "玩游", "写周报", "帮我翻译", "学英语", "推荐几部", "今天好累",
                  "好累", "我不开心", "有点难过", "好无聊", "今天好开心", "下雨", "又加班", "加班",
                  "天气", "外面", "考试", "事情太多", "你叫什么", "你是人", "你是什么", "自我介绍",
                  "你是机器", "你是GPT", "你是Chat", "多谢", "太棒", "厉害", "谢谢你", "好棒",
                  "不错不错", "诗写得真好", "拜拜", "明天见", "回见", "我先走", "下次", "睡了",
                  "去忙", "你住", "你喜欢", "你最喜欢", "李白和"))
    is_creation_request = bool(re.search(r"(写|作|填|来一|读一|续写|补全|题《|为题)", d["instruction"]))
    if chatty and not is_creation_request and re.search(r"(立意：|诗：\n|词：\n|意象解释：)", out):
        errors.append(f"[{i}]闲聊样本带诗词格式")
    if "以上便是" in out or "希望你喜欢" in out:
        errors.append(f"[{i}]客套语")

bad = set(int(e.split("]")[0][1:]) for e in errors)
print("质检问题:", len(errors))
for e in errors[:20]:
    print("  ", e)
data = [d for i, d in enumerate(data) if i not in bad]
random.shuffle(data)
json.dump(data, open(os.path.join(TD, "poemly_sft_v22.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("v2.2 最终:", len(data), "条，已写出 poemly_sft_v22.json")
