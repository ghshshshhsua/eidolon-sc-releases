# Eidolon SC 本地客户端

基于 [Sallyn0225/eidolon-sc](https://github.com/Sallyn0225/eidolon-sc) 改编的非官方角色聊天客户端，让《偶像大师 闪耀色彩》的角色对话在本机继续。提供 Android 独立应用与 Windows 桌面适配；聊天使用自己的 API，本地保存记录、档案和长期记忆。

## Android 1.3.0 使用入口

- 云端检索：设置 → 自带密钥 → 语义检索与本地模型。可选“云端 · 沿用聊天 API”，不需再申请另一把聊天密钥；或填写支持 `/rerank` 的专用接口。
- 若希望避免本地 Qwen 的等待，把同页“独立判断和记忆整理”也切到 API。该模式不运行本地表情分类，立绘使用默认表情；API 请求可能另外计费。
- 语音识别：设置 → 通话 → 语音识别。系统方式优先离线，离线语言不支持时回退系统默认识别；可检查服务和权限、打开系统语音设置。
- 手机没有开放系统识别服务时，可切换“云端语音模型 API”。默认示例使用硅基流动 `FunAudioLLM/SenseVoiceSmall`，也支持相同 `/audio/transcriptions` 协议的接口。需要相应服务商密钥，不能混用不同服务商的密钥。
- 云端模式录音只在本应用内存暂存，停顿后自动提交，单段最多 15 秒；应用不保存录音文件。服务商会收到音频片段。挂断、静音或切后台后不会把迟到的识别结果发送成新消息。
- 云端检索采用快速关键词召回，再用模型做语义筛选；它不会把不同嵌入模型的向量混用，也不要求重新给全量剧情付费建索引。关键词未命中的剧情仍可能无法召回；沿用聊天 API 时会补充中日文关键词以改善召回。云端失败时回到快速关键词，不加载本地检索模型。

[重排接口文档](https://docs.siliconflow.cn/docs/api/rerank-post) · [语音识别接口文档](https://docs.siliconflow.cn/docs/api/audio-transcriptions-post)。未用真实付费密钥验证这些云服务的速度、识别准确率或费用，需由用户配置后实测。

## 项目内容

| 功能 | 实现方式 |
| --- | --- |
| 29 位角色聊天 | 原项目人设、公开剧情资料与对话上下文，支持流式中日文回复 |
| 聊天模型 | 自行填写 DeepSeek 或兼容接口；没有内置聊天大模型或服务商密钥 |
| 语义检索与重排 | 本地 E5 / mmarco，或快速关键词召回 + 云端语义筛选 |
| 判断与长期记忆 | 本地 Qwen3-1.7B，可在设置中选择 API 判断 |
| 立绘与互动 | 动态立绘、好感度、礼物、任务、日历和统计 |
| 语音 | Android 系统或云端识别、可见状态与重试、Fish Audio 角色音色；Windows 另有本地合成适配 |
| 照片与主动搭话 | 配置生图接口后按请求生成；主动搭话需手动开启，可能产生 API 费用 |
| 本机存档 | 聊天、记忆、档案和数据包导入导出；密钥使用系统安全存储 |
| 更新检查 | 关于页面手动检查、每天一次启动检查、版本说明与下载入口 |

角色还原依赖人设、检索到的剧情和记忆共同组织提示词，由所选聊天 API 生成回复。它不是针对每位角色单独训练的聊天模型，效果会受服务商模型和上下文影响。

## 安装与使用

在[公开发布页](https://github.com/ghshshshhsua/eidolon-sc-releases/releases)下载对应文件。

Android 安装 APK 后，在“设置 → 自带密钥”填写聊天接口和模型名；Fish Audio 密钥可稍后添加，不配置时使用文字聊天。最低 Android 8.0 / ARM64，建议保持系统 WebView 更新。完整 APK 含本地模型，约 2 GB；模型初始化还需额外空间，建议预留 8 GB。NNAPI / Vulkan 是否可用取决于设备和驱动，设置中显示实际后端与回退情况。第三方 ORT Extensions 仍有 16 KB 页兼容限制，不能保证所有设备可用。

Windows [0.7.1 更新补丁](https://github.com/ghshshshhsua/eidolon-sc-releases/releases/tag/v1.2.1)适用于已有本地版，不是首次安装器。先退出应用，把更新包内文件覆盖到原 Eidolon-SC 应用目录，再用原入口启动。不要替换或删除 data 目录；补丁不包含记录、密钥或本机运行环境配置。

首次需手动安装带更新入口的版本。Android 在“设置 → 关于 → 应用更新”，Windows 在“连接设置 → 应用更新”检查。启动检查每天最多一次，可关闭；只获取版本元数据，不自动下载、替换或安装。发现新版后打开公开 Release，下载并按系统提示操作。Android 使用相同签名覆盖安装，先导出数据包备份，勿卸载旧版。

## 隐私与数据去向

记录保存在设备。聊天上下文、相关剧情和记忆会发送给你配置的聊天 API；Fish Audio 接收待合成文本；生图服务接收相应提示词。系统语音识别是否完全离线取决于手机服务。

更新检查访问公开 GitHub 清单，不携带账号令牌、聊天记录、API 密钥或设备标识。网络服务仍会接收建立连接所需的常规网络信息。源码和发布包排除个人聊天、账号配置、签名私钥、日志、浏览器资料和本机编译路径；不预装任何个人存档。

## 源码结构与构建

- work/android-app：Java 原生桥接、SQLite / Keystore、模型推理与 Android React 界面。
- work/source/eidolon-sc-main：原项目前端、后端与角色公开配置，保留本地适配。
- outputs/Eidolon-SC/desktop：Electron 窗口、连接设置、更新检查。
- outputs/Eidolon-SC/local：Windows 本地推理与后端适配。

安装 Node 24、JDK 25、Android SDK Platform 36 / Build Tools 36.0.0，设置 JAVA_HOME 和 ANDROID_HOME。完整对应源码包保留公开模型、索引、JNI 和 AAR；解压后执行 work/android-app/build.ps1。Git 开发仓库省略大模型与生成资源，可先从对应 Release 的源码包恢复这些内容。签名私钥始终由维护者本机保管；自行签名的 APK 不能覆盖原签名安装。

重建 JNI 使用 NDK 29.0.14206865 / CMake 3.31.6；运行 work/prepare-android-vulkan-tools.py 和 work/build-android-judge.ps1。llama.cpp 固定来源和 Android 补丁见 cpp/llama-source.json。编译启用路径映射，避免把开发者本机路径带入原生库。

源码验证：node work/test-update-check.mjs；安装前端依赖后运行 TypeScript 检查、Vite 构建、Android assemble / lint。更新界面测试 node work/test-update-ui.cjs 使用临时浏览器数据和模拟更新信息；云端模型与语音回归见 work/test-cloud-models.cjs、test-cloud-ui.cjs 和 test-cloud-native.cjs，不使用真实付费 API。Windows 首次部署仍需自行准备 Python / Electron 与本地模型环境，runtime.json 不随公共发布包分发。

## 开源与素材声明

本改编保留原项目 AGPL-3.0 许可证。开发仓库可私有；公开 Release 同时提供安装包与本版本对应的脱敏源码压缩包。第三方模型、ONNX Runtime、llama.cpp、Spine Runtime 等按各自许可使用，见 work/android-app/THIRD_PARTY_NOTICES.md 和 licenses/。角色、游戏素材与剧情版权属于各自权利人，本项目不代表官方。
