# Android 1.4.3-preview.1

已同步源項目 Sallyn0225/eidolon-sc 的 c4bd0b5b6a4c083ac4ddf93a736175e3a32bc8c2，加入新版格式 3 資料包的匯入相容處理；尚未用使用者的實際匯出包驗證，不能認定格式差異是唯一失敗原因。

## 本次更新

- 資料匯入支援格式 1、2、3，匯出升級為格式 3；支援週期記錄、不適事件及新對話欄位。
- 匯入前完整檢查壓縮包、資料結構與圖片；重複匯入去重，驗證或儲存失敗時保留原有資料。
- 移植日程與每週工作、角色週期與使用者週期記錄、體貼判定、保暖禮物、VA-283 酒吧及成就頁。酒吧包含調酒、對話、重試、歷史及每日獎勵；原版酒吧音樂與音效尚未打包。
- 沿用固定提示詞前綴、原樣重放歷史、檢索與重排快取、並行判定及提前串流；新增的日程、週期和背景主動訊息內容放在固定前綴之後，減少對快取的干擾。
- APK 與模型繼續分開；既有模型包可直接沿用，不必重新下載。

## 安裝

下載下方 **Eidolon-SC-Android-1.4.3-preview.1.apk**。已安裝 1.4.2-preview.1 的使用者可直接覆蓋安裝，保留預覽版資料、設定及模型。這是獨立預覽版，與穩定版使用不同應用識別碼。

新使用者需要的模型包仍位於 [1.4.2-preview.1 發佈頁](https://github.com/ghshshshhsua/eidolon-sc-releases/releases/tag/v1.4.2-preview.1)：

- [檢索模型包](https://github.com/ghshshshhsua/eidolon-sc-releases/releases/download/v1.4.2-preview.1/eidolon-models-retrieval-5d7233bc58fc.zip)
- [判定模型包](https://github.com/ghshshshhsua/eidolon-sc-releases/releases/download/v1.4.2-preview.1/eidolon-models-judge-b3f7bd777fbd.zip)
- [語音模型包](https://github.com/ghshshshhsua/eidolon-sc-releases/releases/download/v1.4.2-preview.1/eidolon-models-speech-59c5055a3322.zip)

## 驗證與已知限制

來源提交的既有驗證紀錄包含 Android 編譯、lint、TypeScript、1,458 項上游前端測試，以及格式相容性、重複匯入、儲存失敗、週期算法、日程、酒吧、快取與模型包回歸測試。本次發佈流程另要求實際 APK 簽名、包名、版本、模型分離和全部發佈檔案 SHA-256 核驗通過。

尚未完成實體手機 UI／音效驗收；未進行付費模型的實際命中率與延遲基準測試，因此不承諾具體提升百分比。此版不替換穩定版更新通道。

完整對應源碼見下方 source.zip；程式碼分支為 [codex/android-1.4.3-upstream-sync](https://github.com/ghshshshhsua/eidolon-sc-client/tree/codex/android-1.4.3-upstream-sync)。

對應源碼提交：[4b70b8c](https://github.com/ghshshshhsua/eidolon-sc-client/commit/4b70b8c62bbcfe2d5e6a86b42d352cd7e10a4321)。
