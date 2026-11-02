# Mizarllm — 仓库规则（Agent 必读）

第六个独立仓库（根 `AGENTS.md` 的工作区地图已列出）：`git@github.com:ShirazuNagisa/Mizarllm.git`，分支 `main`。
内容是「一轮到底完没完」的 1.7B 判定模型（Qwen3-1.7B + LoRA，Q4_K_M）和它的发布元数据。
**权重是发布资产，不是源码。**

## 权重不进仓库

- 不提交 `models/*.gguf`（`.gitignore` 已忽略 `*.gguf`、`*.f16.gguf`、`build/`、`__pycache__/`）。
- 发版 = 打 tag + 把 GGUF 作为 GitHub Release asset 上传。**tag 即版本**：`v1`、`v1.0.0`，之后 `v2`…
  宿主用这个字符串既比较版本，也拼下载地址，改名等于改协议。
- 资产命名 `mizarllm-<version>-q4km.gguf`，配套 `SHA256SUMS` 与 `manifest.json`
  （`file` / `sha256` / `size_bytes` / `labels` / `note`），由 `tools/gen-manifest.py` 生成。
- `manifest.json` 里的 `LABELS` 与 `NOTE` 是手工判断（四态 → 状态码），改它们等于改行为，要和
  `docs/state-codes.md` 一起看。

## 常用命令（与 README 一致）

```sh
# 构建：合并 LoRA → f16 → Q4_K_M（需要 transformers/peft/torch/gguf，以及 llama.cpp 的 llama-quantize）
pip install transformers peft torch sentencepiece gguf
python tools/export_gguf.py --adapter /path/to/mizarllm-v1-lora --out ./build

# 写发布元数据
python tools/gen-manifest.py --gguf build/mizarllm-v1-q4km.gguf --version v1

# 使用：下载 → 校验 → 起服务
gh release download v1.0.0 --repo ShirazuNagisa/Mizarllm --pattern '*.gguf'
sha256sum -c SHA256SUMS
llama-server -m mizarllm-1.0.0-q4km.gguf --port 8791 --ctx-size 4096 -t 4
```

本仓库**没有自动化测试套件**，README 也只给下载/启动命令（以 `README.md` 为准）。
发布前的验证就是：`manifest.json` 的 `sha256` 与实际产物一致，`llama-server` 能加载并返回一次合法判定。

## 许可与数据

- 本仓库与微调权重均为 Apache-2.0（`LICENSE`）；基座 Qwen3-1.7B 也是 Apache-2.0，
  许可证副本 `LICENSES/Qwen3-1.7B.txt`、归因 `NOTICE` —— 发布或再分发时一起保留。
- 训练数据来自 operator 自己的 Agent 会话，**不随仓库分发**；不要把数据集或会话原文提交上来。

## 其他

- 不放密钥 / Token；GitHub 发布凭据只存在 `../docs/servers-ssh.md`，不写进脚本、CI 或提交信息。
- 工作区级文档写 `../docs/mizarllm/`（如 `mizarllm-v1-2026-10-28.md`），不要堆在本仓库里。
- 本仓库 `README.md` / `NOTICE` / `manifest.json` 当前是 `0600`；公开仓库建议统一 `644`（见工作区审计 P4）。
- 本地权重副本在 `../models/`（带 `SHA256SUMS`）；运行时安装位是 `~/.agi-mizar/models/`（`MIZAR_MODEL_DIR` 可覆盖）。

## Workspace wiki

工作区根有本地预编译 Wiki。动本仓代码/发布前先查：

`wiki search "<任务/模块/错误关键词>" --scope mizarllm --limit 5`

没有 `wiki` 命令时用 `node ../tools/wiki/bin/wiki.mjs ...`；规则与 MCP 见根 `AGENTS.md` 的「本地 Wiki」节。
