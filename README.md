# Wan L4 Colab 创作工作流

## 推荐：一键版

[![一键版 · Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/printmybutt/wan-l4-colab/blob/main/%E4%B8%80%E9%94%AE%E7%89%88.ipynb)

**打开「一键版.ipynb」，选择 L4 GPU 和高内存运行时，点击「全部运行」。** 自动完成安装、模型下载、网页和公网隧道启动，最后显示 **HTTPS 地址、账号 owner、自动生成的强密码**。无需修改开关或输入密码。

公网默认开启且强制鉴权，通过本地与公网自检后才显示访问凭据。启动时不自动生成视频；登录网页后提交想法，依次查看文案、首帧和视频。同一运行时重复执行会复用仍正常的服务与密码。

- [一键版笔记本](一键版.ipynb)
- [一键版说明](一键版说明.txt)
- [一键版验证报告](一键版验证报告.json)
- [一键版下载包](一键版下载包.zip)
- [一键版 SHA256 校验](一键版SHA256SUMS.txt)

密码只保留在运行时内存和最终输出，请在分享笔记本前清除运行输出。公网临时地址随 Colab/隧道停止而失效。新文件本身不含真实凭据。**未在 L4/Colab 实际执行，真实公网连通性仍需运行验证。**

## 普通版：按阶段运行


[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/printmybutt/wan-l4-colab/blob/main/Wan_L4_Idea_to_Video.ipynb)

想法 → 中文文案与英文提示词 → 图片 → 官方 Wan2.2 TI2V-5B 图生视频，每一步展示和保存结果。

目标配置：**NVIDIA L4 24GB 显存、64GB 系统内存、200GB 硬盘**。

> **尚未在 L4 或 Colab 上实际执行。** 已通过笔记本格式、代码语法、固定官方 CLI 参数匹配、Linux 依赖解析及 CPU 模拟 API 检查；未实测端到端推理、峰值显存、耗时、最终画质或真实 Cloudflare Tunnel。

## 开始使用

1. 点击上方 **Open in Colab**。
2. 在「运行时 → 更改运行时类型」选择 **L4 GPU**，并启用高内存。
3. 按笔记本顺序运行硬件检查、独立环境安装、CUDA/FlashAttention 自检和模型下载。
4. 修改 `IDEA`，先使用默认 **33 帧、20 步**，依次查看文案、首帧及视频。
5. 短片跑通后可用 **121 帧、50 步**；官方 24 FPS 下约 5.04 秒。
6. 在笔记本第 8 节打包下载结果。Colab 回收会清空 `/content`，请及时保存。

无需向作者提供账号或接入你的 Colab。首次安装和权重下载需要网络与数十 GB 下载空间。

## 模型与功能

| 阶段 | 模型 / 实现 |
| --- | --- |
| 文案 | `Qwen/Qwen2.5-1.5B-Instruct`，BF16 |
| 文生图 | `stabilityai/sd-turbo`，FP16，512×512，4 步，CFG=0 |
| 图生视频 | `Wan-AI/Wan2.2-TI2V-5B`，官方 `generate.py`，1280×704、24 FPS |
| 网页与 API | 可选 FastAPI，统一 HTTP Basic 鉴权，异步任务和轮询进度 |
| 公网入口 | 可选 Cloudflare Quick Tunnel，客户端 SHA256 与鉴权自检 |

- 图片保留原始 512×512 图，并展示居中裁切、放大的 1280×704 实际视频首帧；放大不增加细节。
- 三阶段各自运行于独立进程，结束后释放 CUDA 上下文；文件锁避免同时占用 GPU。
- 保留官方卸载参数 `--offload_model True --convert_model_dtype --t5_cpu`。
- 固定官方源码提交、模型提交、顶层依赖及官方预编译 FlashAttention wheel。
- 包含 RAM / VRAM / 磁盘 / 驱动检查、GPU 小算子检查及 ffprobe 输出检查；这些运行时检查仍需由你的 Colab 执行。
- 不依赖 ComfyUI、自定义节点或付费推理 API。

## 下载速度与 Xet 提示

已补充 `hf-xet==1.8.0`；当前固定 `huggingface-hub==0.30.2` 需要显式安装 Xet 客户端。第 4 节会在独立环境安装并启用它，使用 4 个文件下载线程，并跳过 SD-Turbo 用不到的重复 FP32/单文件权重。

正在使用旧版笔记本时：停止下载，在新单元格执行以下代码，再重跑第 4 节；不用重装整套环境或删除缓存。

```python
import os, subprocess
subprocess.run([
    '/content/wan_l4_lab/venv/bin/python', '-m', 'pip',
    'install', 'hf-xet==1.8.0'
], check=True)
os.environ.pop('HF_HUB_DISABLE_XET', None)
os.environ['HF_XET_CACHE'] = '/content/wan_l4_lab/hf_cache/xet'
```

已完成文件会复用；HTTP/Xet 切换后未完成的大文件可能重新下载。依赖和接口导入已检查，未在 Colab 测速，不保证提速倍数。参见 [Hugging Face 官方 Xet 说明](https://huggingface.co/docs/hub/en/xet/using-xet-storage)。

## Cloudflare 自检失败恢复

如果日志已经出现 `Registered tunnel connection` 且网络预检通过，旧版可能在公网地址尚未就绪时过早关闭隧道。新版先验证本地应用，再分别尝试 auto / HTTP/2，每种协议最多等待 120 秒，显示具体 HTTP 状态和连接错误；仍严格要求匿名 401 / 带密码健康 JSON 200。

已有 Colab 不用重装模型：把 [Cloudflare_Recovery.py](Cloudflare_Recovery.py) 的内容复制到新代码单元格，设置 `ENABLE_PUBLIC=True` 后运行。它复用当前 `BASE` 和 `WEB_AUTH`，只重建此笔记本的隧道，不重启模型服务。失败日志为 `tunnel_auto.log` / `tunnel_http2.log`。

修复经过离线模拟测试；真实公网连通性需在你的 Colab 中验证。

## 默认访问设置

`ENABLE_WEB=False`、`ENABLE_PUBLIC=False`。开启网页时需要隐藏输入至少 16 字符密码；密码不会写入配置。

网页、API 和产物媒体均要求鉴权。公网链接使用 HTTPS，任务通过 HTTP 轮询展示阶段结果，不依赖 Quick Tunnel 不支持的 SSE。服务用于个人临时演示，同一账号可读取本次服务会话的全部产物。

## 文件

- [Colab 笔记本](Wan_L4_Idea_to_Video.ipynb)：独立可用，运行所需辅助源码内嵌于笔记本，无需下载额外附件。
- [运行说明](运行说明.txt)：上传、运行、下载及可选公网入口说明。
- [验证报告](验证报告.json)：已检查项目与未执行项目。
- [完整下载包](Wan_L4_下载包.zip)：笔记本、说明、报告及校验文件。
- [SHA256 校验](SHA256SUMS.txt)：原始交付文件校验和。

## 官方依据与许可

- [Wan 官方仓库](https://github.com/Wan-Video/Wan2.2)及[本笔记本固定源码提交](https://github.com/Wan-Video/Wan2.2/tree/e5058c08fada388b04bb3d1a4734bddbd2fdeac5)
- [Wan2.2 TI2V-5B 官方模型卡](https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B)
- [Qwen 官方模型卡](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct)
- [SD-Turbo 官方模型卡](https://huggingface.co/stabilityai/sd-turbo)
- [Cloudflare Quick Tunnel 文档](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)

模型及依赖遵循各自许可；SD-Turbo 商业用途请核对当前 Stability AI 许可。文案不会自动转为配音或字幕，本项目不含多镜头剪辑、GPU 抢占或保活逻辑。

核对日期：2026-11-26。
