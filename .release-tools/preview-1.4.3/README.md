# 1.4.3 預覽版發佈修補

這份修補接續既有 1.4.3 匯入修復、已簽署 APK、對應原始碼及 byte-delta 重建成果。它不重寫快取統計或匯入功能，也不重新編譯或重新簽名。提交修補、測試通過或執行 verify 均不代表 APK 已發佈。

## 固定輸入

| 項目 | 固定值 |
| --- | --- |
| 發佈倉庫 | `ghshshshhsua/eidolon-sc-releases` |
| 發佈分支 | `codex/publish-1.4.3-preview` |
| 來源分支 | `ghshshshhsua/eidolon-sc-client` 的 `codex/android-1.4.3-upstream-sync` |
| 來源提交 | `4b70b8c62bbcfe2d5e6a86b42d352cd7e10a4321` |
| 版本／標籤 | `1.4.3-preview.1`／`v1.4.3-preview.1` |
| 包名／versionCode | `local.eidolon.sc.android.preview`／`143` |
| 簽名憑證 SHA-256 | `4c7ab53572c7ecc4b76517edf404a834bc955bd0b8bf9d5296a868e6045b1c31` |
| 正式更新清單 | `main:updates/stable.json`，blob `64876f05ff3a4fc2d0549c17bfdca66412716185` |

`SHA256.json` 保留已完成的 APK 與完整對應原始碼之大小及 SHA-256。`payload-descriptor.json` 沿用 2026-10-29 續作紀錄中的 20 片 payload 描述；舊的、不相容的 payload 分片不能混用。發佈前核對每片、完整 payload、基底檔案及重建輸出的摘要。

## 執行前置條件

1. **既有 payload**：將已保存的 `publication-payload.zip` 按 `payload-descriptor.json` 拆為 `payload/part-000.bin` 到 `part-019.bin`，放在本目錄。修補只含程式碼與描述，沒有公開這些分片、APK 或對應原始碼。原 payload 為 10,311,109 bytes，SHA-256 `f106af8f710fd8b564fad60332e6cfd54679c9e9117efaaf1654651a506c198a`。分片須另經既有公開發佈授權程序後上傳；缺片時工作流程明確失敗，不建立草稿。
2. **簽名**：此次使用已簽好的固定 APK，不需把簽名私鑰或密碼交給 Actions。工作流程以 `apksigner verify` 驗證新舊兩個 APK，兩者都必須只有上述同一憑證，並要求包名相同、版本從 142 增至 143、非 debuggable。憑證欄位不能代替驗證。如果重新編譯，必須持有原預覽版私鑰及密碼；不可新建金鑰冒充覆蓋升級包，也不可用正式版金鑰或 debug 金鑰。簽名失敗會停止。此修補沒有確認私鑰目前仍可取得。
3. **GitHub 權限**：套用工作流程需能寫入此倉庫的分支與 `.github/workflows`（PAT／App 的 Contents: write 及所需 Workflows 權限）。執行者須能手動觸發 Actions；倉庫／組織政策須允許 release job 的 `GITHUB_TOKEN` 使用 `contents: write`，並允許建立此標籤和 Release。測試 job 只有 `contents: read`。不需私有來源倉庫 token，因輸入是固定且已核驗的對應原始碼包。
4. **工作流程註冊**：將這個工作流程合併進預設 `main` 後，才會提供 `workflow_dispatch`。在 Actions 選擇 `codex/publish-1.4.3-preview` 分支執行；從其他分支手動執行會跳過 release job。保留該分支的發佈提交，重跑時必須使用同一提交。
5. **Runner**：Ubuntu 24.04、Python 3.11+、Java、GitHub CLI、curl、Android SDK Build Tools 36.0.0，以及至少約 8 GB 可用空間。需要連至 GitHub API／release 資產網域及 Android SDK 下載站。建議預留 12 GB。工作流程會安裝核驗工具；工具不可用時停止，不能略過核驗。

## 操作與結果

推送修補／建立 PR 只跑離線模擬測試。合併並準備好 payload 後，先手動選 `mode=verify`；成功時只輸出 `verified-only` 和 `published: false`，不呼叫任何 Release 寫入 API。確認完整核驗通過後才選 `mode=publish`。

也可以在已有檔案的受控環境核驗：

```bash
python3 .release-tools/preview-1.4.3/publish.py \
  --staging /path/to/exact-three-assets \
  --baseline-dir /path/to/previous-apk
```

staging 必須恰好含新版 APK、對應原始碼 ZIP 和本修補的 `SHA256.json`。上述命令只驗證。`--publish` 額外要求正確的 Actions repository/ref/event/SHA/token 環境，不應在不受控的環境手動偽造。

實際發佈程式按標籤分頁尋找草稿，不使用舊 Release ID。新草稿設為 `prerelease: true`、`make_latest: false`，所有資產核驗完成才將 `draft` 改為 false。只會上傳 APK、對應原始碼和 SHA256.json；judge／retrieval／speech 模型包沿用公開 1.4.2 預覽版，發佈前另核對三個現有遠端模型資產的狀態、大小及摘要。

每個遠端資產必須 `state=uploaded` 且大小、SHA-256 完全一致。完整已發佈版本的重跑為唯讀；部分草稿只補缺少的資產。僅允許刪除同一草稿中零 bytes、無 digest 的 `starter` 殘留；同名內容不符、未知資產、重複名稱、缺失 digest、已公開但不完整、來源／標籤不符皆停止，不覆寫。上傳回應遺失或 API 失敗後，可重跑**相同提交**，重新讀取伺服器狀態。

腳本沒有寫入 stable.json 的 API；發佈前、過程中和發佈後都比對其固定 blob，並確認 `/releases/latest` 未變。外部維護者同時更新正式通道時會停止，不回復其改動。若公開後最後核驗失敗，Release 可能已公開；退出碼仍為 1，應檢查遠端後再重跑，不把錯誤訊息解讀為回滾成功。

## 核驗範圍

- 固定來源關鍵檔案的 Git blob 雜湊，包括已提交的 `dataPackage.ts`、匯入整合測試、預覽版 Gradle 設定、更新通道隔離程式及相容性說明；原始碼 ZIP 全檔摘要和 CRC。
- 實際 APK 簽名、包名、版本、非 debug 屬性與 ZIP 對齊。
- APK 不含 GGUF、ONNX、neural BIN、離線語音 model.zip 或 semantic.db；保留 corpus.db 和 tokenizer。模型清單必須與固定來源一致。
- Release 標籤、對應發佈提交、來源標記、三個資產、草稿／預覽狀態、latest 及正式更新清單。

## 測試

```bash
python3 -m unittest discover -s .release-tools/preview-1.4.3 -p 'test_*.py' -v
```

測試以模擬 API 回應驗證首次發佈、重跑、部分上傳、回應遺失、starter 清理、401／403／502、錯誤摘要、分頁、標籤衝突、正式通道變動及非零退出。APK 身份／簽名解析以模擬 SDK 輸出測試；這不是實際 APK 簽名驗證或真機安裝測試。核驗腳本會在正式執行時呼叫真正的 Android 工具。

上次匯入和應用回歸成果保留於來源提交的 `UPSTREAM-1.4.3.md`，這次沒有重做那些功能。尚未取得使用者的實際匯出包，不能認定格式差異是唯一匯入失敗原因。

參考：[GitHub Release API](https://docs.github.com/en/rest/releases/releases)、[Release assets API](https://docs.github.com/en/rest/releases/assets)、[Android apksigner](https://developer.android.com/tools/apksigner)。
