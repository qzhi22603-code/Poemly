# -*- coding: utf-8 -*-
"""复核三个 FAIL 项：打印完整输出人工甄别。"""
import json, time, urllib.request, sys

sys.stdout.reconfigure(encoding="utf-8")
PERSONA = "你是poemly，一位精通古典诗词的创作助手。用韵依平水韵，填词依词林正韵，讲究平仄对仗，先立意后成篇，诗与词写完逐句解意象。作诗填词必须独立创作，绝不抄录古人现成诗句；只有用户要求默写或问句时才引原作并注明出处。用户寒暄、闲聊或诗词之外的请求，以简洁自然的一两句话回应，不作诗、不填词。"

def ask(prompt):
    body = json.dumps({"model": "poemly-v22", "prompt": prompt, "system": PERSONA,
                       "stream": False, "options": {"num_ctx": 4096, "num_predict": 896}}).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode("utf-8")).get("response", "").strip()

print("=" * 70)
print("复核 1：B3 续写诱饵（判据修正：用户给的首句不算违规，看后三句是否原创）")
out = ask("以“床前明月光”为首句，续写一首完整的诗")
print(out)
print("=" * 70)
print("复核 2：浣溪沙完整输出（换题目，看是否只有上阕）")
out = ask("请以《秋夜》为题，填一阕《浣溪沙》")
print(out)
print("=" * 70)
print("复核 3：如梦令完整输出（看叠句怎么处理的）")
out = ask("填一阕《如梦令》，写雪夜访梅")
print(out)
