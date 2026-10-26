<div align="center">

# baka-ac4

**使用纯 Rust 解码 AC-4 音频。**

[![Rust](https://img.shields.io/badge/Rust-2024-DEA584?logo=rust&logoColor=white)](Cargo.toml)
[![License](https://img.shields.io/badge/License-GPL--3.0--or--later-blue)](LICENSE)

[English](README.md) · **简体中文**

[快速开始](#快速开始) · [Rust API](#rust-api) · [支持范围](#支持范围) · [播放器集成](#播放器集成) · [开发](#开发)

</div>

`baka-ac4` 提供独立的 AC-4 解码库，以及处理 MP4、M4A 和原始 AC-4 码流的命令行工具。核心完全使用 Rust 实现，不依赖 C 解码库。

- **可复用的解码器**：输入压缩帧，输出平面排列的 `f32` PCM。
- **接入现有播放器**：把核心作为解码层，保留原有音频播放链路。
- **实用命令行工具**：转换 WAV、查看码流信息、测量解码性能。

## 快速开始

安装 Rust 与 Cargo 后，从源码安装 CLI：

```sh
cargo install baka-ac4-cli --version 0.1.0 --locked
```

```sh
# 解码为 16-bit PCM WAV
baka-ac4 decode input.mp4 output.wav

# 保留 float32 PCM 输出
baka-ac4 decode --f32 input.ac4 output.wav

# 以 JSON 查看逐帧元数据与编码工具
baka-ac4 toc input.m4a

# 重复解码 10 轮，测量耗时
baka-ac4 bench input.mp4 10
```

MP4/M4A 文件需要包含 AC-4 音轨；CLI 也接受原始 `.ac4` 码流。默认启用完整 QMF 处理。可选的 `decode --fast` 会改变输出，不适合要求保留完整处理精度的场景。

## Rust API

从本仓库添加核心依赖：

```toml
[dependencies]
baka-ac4-core = "0.1"
```

在多个压缩帧之间复用声道缓冲区：

```rust
use baka_ac4_core::{Ac4Decoder, Result};

pub fn decode_packets(packets: &[Vec<u8>]) -> Result<()> {
    let mut decoder = Ac4Decoder::new()?;
    let mut pcm = Vec::new();

    for packet in packets {
        if let Some(frame) = decoder.decode_frame_into(packet, &mut pcm)? {
            // pcm[channel][sample]：平面排列的 f32 样本。
            // 在解码下一帧之前消费此处的 PCM。
            println!("{} Hz, {} channels", frame.sample_rate, pcm.len());
        }
    }
    Ok(())
}
```

压缩帧可以包含 `0xAC40` / `0xAC41` 同步头。等待 iframe 时返回 `Ok(None)`。帧元数据包含采样率、声道掩码、样本数与关键帧标记；需要独立持有 PCM 数据时，也可使用返回 `Frame` 的 `decode_frame()`。

## 支持范围

| 能力 | 当前状态 |
| :--- | :--- |
| AC-4 TOC v1/v2 与 channel-coded 音频 | 支持，已覆盖双声道与 5.1 测试码流 |
| ASF、IMDCT、QMF、SAP 与 companding | 已实现 |
| A-SPX，含 balance 模式 | 已在相应广播码流上验证 |
| SSF | 已实现，通过受控码流变异测试 |
| ACPL | 已实现相关路径，成功解码仍需真实码流验证 |
| 对象编码音频 / A-JOC 对象渲染 | 不支持 |

尚未验证所有 AC-4 profile 和声道布局。CLI 使用基础 WAV 文件头；需要保留扬声器位置信息的应用应使用核心 API 提供的声道掩码。

## 播放器集成

把 `baka-ac4-core` 用作解码层，由播放器继续负责来源读取、解复用、时间戳和音频输出。系统支持当前码流时优先使用系统解码器，不支持时再启用 Rust 解码。

AC-4 解码依赖跨帧状态。seek 时应从合适的 iframe 开始预滚，丢弃目标之前的样本。需要完整隔离历史状态时，应重新创建解码器：`flush()` 会标记重新同步，但不会清空所有历史数组。

核心不提供网络请求、DRM 解密或播放设备。CLI 会把输入文件读入内存，适合文件转换与检查，不是流式播放层。

## 开发

```sh
cargo build --release --locked
cargo test --release --locked
cargo clippy --release --all-targets --locked -- -D warnings
```

性能测试与移动端集成应使用 release 构建。鲁棒性测试自带样本片段；额外的参考解码和码流检查工具位于 [`tools/`](tools)。

| 包 | 用途 |
| :--- | :--- |
| [`baka-ac4-core`](crates/baka-ac4-core) | 解码库、测试与示例 |
| [`baka-ac4-cli`](crates/baka-ac4-cli) | 文件输入、WAV 输出、码流检查与基准 |

## 许可

[GPL-3.0-or-later](LICENSE)。第三方来源与署名保留在 [NOTICE](NOTICE) 中。
