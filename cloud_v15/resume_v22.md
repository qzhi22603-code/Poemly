# v2.2 云训续跑手册（2026-11-16 暂停，回家网络恢复后继续）

## 一、材料清单与位置（全部保全完毕）

| 材料 | 位置 | 状态 |
|---|---|---|
| 训练数据集 poemly_sft_v22.json（2644 条） | GitHub `训练数据/` | ✓ 已入库 |
| 数据生成器 gen_v22.py（含 16 首合律骨架词） | GitHub `训练数据/` | ✓ 已入库 |
| 反抄袭诱饵测试 bait_test_v22.py + 复测结果 | GitHub `训练数据/` | ✓ 已入库 |
| 训练脚本 train_v22.py（v2.2 人设，含闲聊分流指令） | GitHub `cloud_v15/` | ✓ 已入库 |
| 合并脚本 merge_v22.py | GitHub `cloud_v15/` | ✓ 已入库 |
| 一键自举 bootstrap_v22.sh | GitHub `cloud_v15/` | ✓ 已入库 |
| 部署配置 Modelfile-v22（SYSTEM 与训练逐字一致） | 仓库根目录 | ✓ 已入库 |
| 诗阁前端（D2 上下文/D3 平仄自查已上线） | GitHub 根目录 + 桌面 | ✓ 已入库 |
| 本地全部源码 | `C:\Users\38107\Desktop\ai` | ✓ 完整 |

## 二、本次实例状态（b63c498021-3fa58474d，RTX 2080 Ti 重庆A区）

- 关机时间：2026-11-16 约 21:00，进度停在 [1] torch 安装
- **按量实例关机 15 天后自动释放**。释放了也完全无所谓：实例里没有任何不可再生物（底模可重新下载、脚本可重新拉取、数据在 GitHub），下次租新机照样一条龙
- 环境损坏残骸：该实例 site-packages 有 pip 元数据损坏（双实例并行安装所致），**下次开机建议先跑下面的"环境修复"，或直接用新实例**

## 三、下次云训操作（三条命令接上）

1. 租卡（RTX 4090 24GB 优先，¥2/h 级；镜像「框架镜像→PyTorch 2.8.0→CUDA 12.8」）
2. Jupyter 终端依次执行：

```bash
wget https://raw.githubusercontent.com/qzhi22603-code/Poemly/main/cloud_v15/bootstrap_v22.sh -O /root/b22.sh
```

```bash
nohup bash /root/b22.sh > /dev/null 2>&1 &
```

```bash
tail -f /root/autodl-tmp/t22f.log
```

3. 开跑约 1-2 分钟后，装日志上报器（供本地监控）：

```bash
wget -qO /root/up_gist.py https://raw.githubusercontent.com/qzhi22603-code/Poemly/main/cloud_v15/up_gist.py && source /etc/network_turbo 2>/dev/null; nohup bash -c 'while true; do python3 /root/up_gist.py gho_此处填你的GitHub令牌; sleep 120; done' > /root/up_gist.log 2>&1 &
```

4. 本地恢复监控：唤醒 Schedule 任务「poemly-v2.2 训练进度监控」（paused 状态，resume 即可）
5. 训练量化完成后：立刻关机 → 下载 `/root/autodl-tmp/poemly-v22-Q6_K.gguf` → 通知主会话做阶段三验收

## 四、本次踩坑记录（血泪教训，勿重蹈）

1. **双实例并行**：nohup 启动命令重复执行会开两个实例抢卡，pip 互相写坏 site-packages 元数据（TypeError NoneType + invalid distribution），最终 pip 崩溃退出。→ 启动后必须 `ps aux | grep b22` 确认只有一个；重复粘贴 = 灾难
2. **pip 损坏修复命令**（2026-11-16 实测有效）：

```bash
pkill -9 -f "b22\.sh"; pkill -9 -f "pip install"; find /root/miniconda3/lib/python3.12/site-packages -maxdepth 1 -name '~*' -exec rm -rf {} + ; rm -rf /root/miniconda3/lib/python3.12/site-packages/distutils_hack; python3 -m pip install -q --force-reinstall --no-deps pip setuptools -i https://mirrors.aliyun.com/pypi/simple/ && python3 -m pip install -q --force-reinstall torch -i https://mirrors.aliyun.com/pypi/simple/ && nohup bash /root/b22.sh > /dev/null 2>&1 &
```

3. **2080 Ti 网络实测**：出口约 1.6MB/s，torch 全家桶（8GB，含 CUDA 运行库）下载约 80 分钟——是带宽天花板不是故障，判断标准看 AutoPanel 硬盘曲线是否持续上涨
4. **ALL_DONE 铁律**：量化完成立刻关机，一分钟都别多挂（v2.1 曾因挂机烧 ¥55）
5. 本地 hosts 的 github.com 加速 IP 已失效（20.200.245.247），git push 会挂——用管理员记事本删除 hosts 中 github.com 三行可修复；或临时用 `upload_via_api.py`（Contents API + 真实 IP）应急上传

## 五、v2.2 待办（下次云训后）

- [ ] 四项验收盲测：词牌格律 / 闲聊分流 / 反抄袭（重跑 bait_test）/ 诗创作回归
- [ ] 诗阁切换 poemly-v22 模型名
- [ ] 迭代图谱补 v2.2 行 + GitHub Release v2.2（模型分卷 + 校验值）
- [ ] 本地格律检查器数据（可选，为 v3.0 教育版蓄力）
