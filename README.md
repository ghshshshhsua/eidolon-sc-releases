# Eidolon SC 本地客户端

基于 [Sallyn0225/eidolon-sc](https://github.com/Sallyn0225/eidolon-sc) 改编的非官方角色聊天客户端，让《偶像大师 闪耀色彩》的角色对话在本机继续。提供 Android 独立应用与 Windows 桌面适配；聊天使用自己的 API，本地保存记录、档案和长期记忆。

## 项目内容

| 功能 | 实现方式 |
| --- | --- |
| 29 位角色聊天 | 原项目人设、公开剧情资料与对话上下文，支持流式中日文回复 |
| 聊天模型 | 自行填写 DeepSeek 或兼容接口；没有内置聊天大模型或服务商密钥 |
| 语义检索与重排 | 本地 E5 与 mmarco，检索相关剧情和角色记忆 |
| 判断与长期记忆 | 本地 Qwen3-1.7B，可在设置中选择 API 判断 |
| 立绘与互动 | 动态立绘、好感度、礼物、任务、日历和统计 |
| 语音 | Android 系统语音识别、Fish Audio 角色音色；Windows 另有本地合成适配 |
| 照片与主动搭话 | 配置生图接口后按请求生成；主动搭话需手动开启，可能产生 API 费用 |
| 本机存档 | 聊天、记忆、档案和数据包导入导出；密钥使用系统安全存储 |
| 更新检查 | 关于页面手动检查、每天一次启动检查、版本说明与下载入口 |

角色还原依赖人设、检索到的剧情和记忆共同组织提示词，由所选聊天 API 生成回复。它不是针对每位角色单独训练的聊天模型，效果会受服务商模型和上下文影响。

## 安装与使用

在[公开发布页](https://github.com/ghshshshhsua/eidolon-sc-releases/releases)下载对应文件。

Android 安装 APK 后，在“设置 → 自带密钥”填写聊天接口和模型名；Fish Audio 密钥可稍后添加，不配置时使用文字聊天。最低 Android 8.0 / ARM64，建议保持系统 WebView 更新。完整 APK 含本地模型，约 2 GB；模型初始化还需额外空间，建议预留 8 GB。NNAPI / Vulkan 是否可用取决于设备和驱动，设置中显示实际后端与回退情况。第三方 ORT Extensions 仍有 16 KB 页兼容限制，不能保证所有设备可用。

Windows 0.7.1 是已有本地版的更新补丁，不是首次安装器。先退出应用，把更新包内文件覆盖到原 Eidolon-SC 应用目录，再用原入口启动。不要替换或删除 data 目录；补丁不包含记录、密钥或本机运行环境配置。

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

源码验证：node work/test-update-check.mjs；安装前端依赖后运行 TypeScript 检查、Vite 构建、Android assemble / lint。更新界面测试 node work/test-update-ui.cjs 使用临时浏览器数据和模拟更新信息，不使用真实付费 API。Windows 首次部署仍需自行准备 Python / Electron 与本地模型环境，runtime.json 不随公共发布包分发。

## 开源与素材声明

本改编保留原项目 AGPL-3.0 许可证。开发仓库可私有；公开 Release 同时提供安装包与本版本对应的脱敏源码压缩包。第三方模型、ONNX Runtime、llama.cpp、Spine Runtime 等按各自许可使用，见 work/android-app/THIRD_PARTY_NOTICES.md 和 licenses/。角色、游戏素材与剧情版权属于各自权利人，本项目不代表官方。
