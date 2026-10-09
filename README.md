# 方舟智慧體

啟用 AI 的正式網站：https://ark-agent.fanhow.chatgpt.site/

公開盤勢／靜態備用網站：https://fanhow.github.io/ark-agent/

GitHub Pages 版可直接使用，庫存、CSV 與照片儲存於各自瀏覽器的 IndexedDB，可下載／還原備份。本機版仍提供 Python 後端與 AI 代理。

本機的台股／美股 ETF 盤前日誌與庫存複盤工具。原生 HTML、CSS、JavaScript，加上 Python 標準函式庫伺服器，不需要 npm install 或打包。所有端點僅綁定 `127.0.0.1`。

## 啟動

需要 Python 3.11 或更新版本。本機已使用 Python 3.14 驗證。

雙擊 `start.command`，或在 Terminal 執行：

```sh
cd ark-agent
python3 server.py
```

開啟 <http://127.0.0.1:8765>。終端機按 Ctrl+C 停止。若 8765 已被本專案占用，可直接開啟網址；需要不同連接埠時用 `python3 server.py --port 8766`。服務只能從這台電腦存取；400px 手機版驗收指響應式版面，不開放區域網路。

`start.command` 會沿用目前 shell 的 Python；如找不到 Python，使用 系統安裝的 Python 3.11 或更新版本執行 `server.py`。

## 啟用 AI

AI 聊天、截圖／非標準文字辨識、每日人物推演與複盤使用專用 OpenAI API 金鑰。本機 `.env` 設定 `AI_PROVIDER=openai`、`OPENAI_API_KEY` 與 `OPENAI_MODEL`（預設 `gpt-4.1-mini`）。金鑰透過 OpenAI Developers 的安全建立流程寫入；不要把金鑰貼入網站、README 或聊天。ChatGPT 聊天會員不會自動為本專案提供 API 金鑰或額度。

`.env` 僅由後端讀取，環境變數優先。只解析 AI 提供者、金鑰與模型設定，不執行 shell。既有 Anthropic 設定保留相容性，選用時設定 `AI_PROVIDER=anthropic`。

OpenAI 使用 [Responses API](https://developers.openai.com/api/docs/guides/text)、圖片輸入與串流，設定 `store:false`；未完成或長度遭截斷的內容不會當作成功回覆。2026-10-08 已建立專用金鑰並接通 Sites 與 GitHub Actions；已驗證真實 API、正式網站聊天及雲端每日研究。每次使用仍取決於帳戶模型權限與 API 額度。

## 每日執行與排程

手動立即擷取（無 AI 金鑰也可）：

```sh
python3 scripts/daily_brief.py
```

使用與排程相同的交易日檢查：

```sh
python3 scripts/daily_brief.py --scheduled
```

單日重跑：`python3 scripts/daily_brief.py --date 2026-10-08`。加 `--notify` 可嘗試 macOS 本機通知，是否顯示由系統權限決定。網站「更新盤勢」按鈕也是同一擷取流程。

本次已建立並啟用 **Codex 自動化「方舟智慧體每日盤前彙整」**，週一至五 **07:52，Asia/Taipei**，識別碼 `automation`。在 Codex 的該自動化卡片編輯時間或停用。這是本機 Codex 排程；電腦與 Codex 必須處於可執行狀態，不保證關機、睡眠或應用程式關閉期間準時執行。若改變系統時區，請重新核對自動化顯示的時間；每日腳本的資料日期始終用 Asia/Taipei。

排程已設定，手動交易日流程已實測；交付時尚未到第一次 07:52，因此不把排程註冊成功描述為已驗證未來準時喚醒。`data/schedule.json` 留存設定摘要。

程式每次向 [TWSE 官方開休市日曆](https://www.twse.com.tw/rwd/zh/holidaySchedule/holidaySchedule?response=json&queryYear=115) 確認交易日；休市跳過、日曆失敗則不猜測，記錄 `blocked`。年度日曆不涵蓋所有臨時停市，仍須以當日官方公告為準。休市測試可用 `--scheduled --date 2026-10-09`。

`--scheduled` 不依賴網頁 server，亦可供 launchd／cron／Windows 工作排程器呼叫；跨平台排程器須另設台北時間，並先停用 Codex 自動化避免重複執行。本次未另外安裝 OS 排程工作。

## 資料位置

所有個人資料位於本專案 `data/`，未發布到網路：

- `data/portfolio.json`：目前庫存、日期、Day、總損益與水位規則。
- `data/portfolio.initial.json`：未改動的講義初始備份。
- `data/briefs/YYYY-MM-DD.json`：每日真實來源彙整；同日重跑更新同一檔案。
- `data/journal/YYYY-MM-DD.json`：以庫存資料日期儲存的複盤；同日覆寫前先備份。
- `data/history/`：庫存或日誌更新前的備份。
- `data/avatars/<id>.jpg` 與 `data/avatars.json`：自行上傳的照片與對應。
- `data/uploads/`：依 SHA-256 命名的原始上傳及 metadata。移除預覽檔案不刪原始本機備份；不需要時可自行刪除這個目錄的檔案。
- `data/cache/`：官方年度交易日曆擷取記錄。
- `data/last-run.json`：最後一次流程完成、跳過或受阻的狀態。

備份整個 `data/` 即可保留個人紀錄；不要將 `.env` 一併公開。可使用 `ARK_DATA_DIR` 指向另一個私人資料目錄；測試採此機制隔離正式資料。

## 初始資料與匯入規則

**講義初始資料・待確認**：暱稱「奶啾哥」、2026-09-30、Day 339、18 檔持股與總損益 -5,024 皆是講義設定，尚未確認歸屬於本次使用者。未改為今日，也未補算未知數字。0056 報酬率為 `null`、損益為 `0`。

- `ret` 使用百分比數值，`-22.73` 表示 `-22.73%`。
- P1 → P3 → P2 採互斥判斷；其餘正常持有，未知報酬率待更新。
- 水位分組不是交易指令，沒有下單或交易執行功能。
- CSV 先 UTF-8，失敗改 Big5／CP950；代號保留前導零。建議欄名：`code,name,shares,ret,pnl,value,asOf,totalPnl,note`；支援「代號、名稱、股數、報酬率、未實現損益、市值、日期、總損益、備註」等常見名稱。
- 缺值留白，不能用 0 代替。只有明確的總計欄才可更新總損益，不把少數已知部位加總成整體總損益。
- 多檔以內容雜湊排重；截圖每批最多 3 張且限制總容量。同代號後來非空值補上，不同資料日期停止合併並要求分開匯入。
- CSV 日期未提供時，預覽必須手動補齊。辨識結果從不直接寫入庫存；按「確認更新庫存」才存檔。
- 辨識檔數低於現有 70% 時預設局部更新。局部更新若總損益未知，保留原總額並註明舊日期；完整取代則可保留 `null`。
- 較新日期 Day +1，同日期不增加；較舊日期須在預覽勾選接受且保留 Day。手動編輯會阻擋較舊日期，請改用匯入預覽。
- 長條圖以 0 為中心、±30% 為視覺尺度，超出封頂；數字保留真實值。
- 「P1 連續未執行」不能由兩期持股推斷，尚缺交易紀錄；「崩跌日不做決策」缺崩跌定義及規則優先順序。AI 提示詞要求標示待確認，不自行選擇交易動作。

## 真實來源與目前限制

已接通 TWSE 加權指數與台積電、Yahoo Finance 美股已收盤日 K（S&P 500／Nasdaq／Dow／SOX）、FRED 10 年債殖利率、紐約 Fed EFFR、BLS／BEA 排程、Fed 已發布演說與 FOMC 日曆。EFFR 是有效利率，不是假稱目標區間。

每項市場資料都有來源、觀測日期與台北擷取時間；只取已收盤美股。深夜手動執行時，當晚美股尚未收盤，會使用更早的已收盤資料並顯示正確日期。利率可能有發布延遲，不稱為即時數值。

Apple Podcasts `id1569167575` 已經 lookup 核實為「方舟運算」，SoundOn RSS 可取得最新集數與簡介。沒有收聽／轉錄音訊；若簡介只有宣傳文，不臆測集數內容。Spotify `3EQjppnFKDfrEJRSOAENdN` 目前未核實可用；Threads `@arkerationapp` 與 App 會員看板未讀取。

**每日研究目前是部分覆蓋，不是完整投資研究**：總經市場預期值、已公布實際值的完整整理、ISM、初領失業金、零售、台灣出口、央行、外資與重大國際事件仍需可靠來源或資料 API。每日日誌會保留這些缺漏。官方排程的空白不代表今天沒有事件。FOMC 日曆未載發布時刻時，`time` 留 `null`。

8 位人物名稱、角色及框架沿用講義，未用作現職查核。無金鑰時只有框架說明，人物當日立場留 `null` 並置於羅盤「待更新」區，不假裝已取得 AI 意見。

## 驗證

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/frontend.test.js
```

瀏覽器驗收腳本 `tests/browser.cjs` 使用 Playwright 與安裝的 Google Chrome；本機使用 Codex bundled Playwright。其他環境可用 `ARK_PLAYWRIGHT` 指向 Playwright 模組。

```sh
node tests/browser.cjs
```

測試使用暫存資料庫、暫時連接埠與明確標示的 AI 模擬回應；不更改正式庫存、不呼叫付費 API。**模擬串流測試通過不代表真實圖片辨識或 AI 品質已驗收**。詳見 `ACCEPTANCE.md`。


## GitHub Pages 版

線上版將公開盤勢與私人庫存分開。`public/briefs/` 僅包含市場、官方排程、公開節目與框架資料；每位使用者的持股、照片與匯入檔案留在自己的瀏覽器，不寫回 GitHub。換裝置前請使用「下載備份」，在新裝置「還原備份」。清除網站資料會移除瀏覽器紀錄。初次開啟仍載入標示「講義初始資料・待確認」的原稿範例，並非實際使用者持股。

建置指令：

```sh
python3 scripts/build_pages.py
```

`site/` 只複製明確白名單的前端檔案、示意頭像、講義 seed 與 `public/briefs/`。不會複製私人 `data/portfolio.json`、`.env`、上傳檔或本機照片。

`.github/workflows/pages.yml` 已設定 push／手動部署，以及台北時間週一至五 07:52 的日報更新。排程先查交易日，成功後保存公開歷史並重新部署。GitHub Actions 排程可能延遲，不保證準時啟動；[官方排程說明](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)。目前本機 Codex 排程繼續更新本機版，雲端工作更新線上版，兩者資料位置各自獨立。

GitHub Pages 提供靜態託管，線上版目前沒有互動 AI 代理；聊天、截圖辨識與 AI 複盤會提示尚未啟用。可在 repository 的 Actions secret 設定 `OPENAI_API_KEY`，供雲端每日研究產生公開框架推演；這不會啟用使用者即時聊天。即時 AI 功能需另行部署有驗證與金鑰保護的後端，前端不可放金鑰。[GitHub Pages 官方說明](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)。

## ChatGPT Sites 版

正式互動功能使用 https://ark-agent.fanhow.chatgpt.site/ ，以獲邀的 ChatGPT 帳號登入。Sites 後端保管金鑰，提供聊天、截圖辨識與 AI 複盤。GitHub Pages 保留公開市場資料與瀏覽器資料工具。

兩個網域的瀏覽器資料獨立；用「下載備份／還原備份」轉移。Sites 同樣不把持股、個人照片或日誌寫回 GitHub。外部獲邀帳號可以使用網站；Sites 編輯者需為同一工作區的有效成員。

AI 立場允許 `null`，不會硬改為中性。每日研究只送來源證據給 AI，拒絕將舊的待更新文字當作新分析。複盤固定沿用設定的水位分組，存檔前檢查新數字與水位清單；此檢查不能取代人工核對。


### 跨資產與穩盈研究入口（2026-10-08）

今日盤勢新增「避險資產與總經雷達」：GC=F 黃金期貨、WTI 原油現貨、USD/JPY、VIX、10 年實質殖利率、Chicago Fed NFCI 與 Fed 廣義美元指數。FRED 序列與 Yahoo 黃金日 K 由原有交易日排程擷取，不需新增金鑰；缺值保留 null。每張卡保留觀測日、比較日、擷取時間、單位與來源，走勢最多 21 筆，各圖獨立刻度。

百分比報酬採相鄰有效觀測；殖利率變動以基點顯示，VIX 以點顯示，NFCI 為每週標準化指數。USD/JPY 下跌代表日圓升值；箭頭僅表示數值方向。黃金保守排除交易所當日日 K，且連續期貨可能換月，不當成現貨或可實現持有報酬。這是最新可取得資料，並非 point-in-time 回測資料。

穩盈完整市場情緒研究直接連到 https://stable-value.fanhow.chatgpt.site/sentiment ，保留原站登入權限，沒有複製私人研究內容到 GitHub，也不宣稱兩站即時同步。「請船員解讀這些指標」預填問題並選取 Dalio、Marks、Druckenmiller；送出後使用目前日報證據，不把外部連結當成已讀內容。

單元測試涵蓋 FX 方向、利率基點、VIX 點數、負值金融情勢、未收盤期貨排除、缺值與單一來源失敗。AI 複盤數字檢查接受新指標的已提供數值，繼續阻擋憑空新增價位。

## 共用資料與每日照片更新

成員網址：https://ark-agent.fanhow.chatgpt.site/

以管理員帳號在網站「共用庫存複盤」上傳庫存照片，辨識後核對累積損益、股數及實際資料日期，再按「確認更新庫存」。長截圖會自動分段；預設只更新辨識到的持股，其餘保留。累積損益未辨識到時沿用上次金額並註明待核對，不會用今日損益代替。其他成員每 15 秒自動讀取共用更新；各自的聊天紀錄不共用。

本機版仍可編輯。`shared_sync.py` 使用 `.env` 中的 Site service token 與獨立同步 secret，每 15 秒檢查共用版本：上傳本機變更，或在本機未修改時接收線上管理員的變更。雙方同時修改時保留雙方版本並顯示衝突，不會靜默覆寫。未連線的變更留在本機重試；成功需通過雲端回讀比對。

本機的同步狀態在 `data/shared-sync.json`，與所有個人資料和 `.env` 一樣排除於 Git。隔離測試的 ARK_DATA_DIR 不啟用正式同步。每日研究成功後也會嘗試同步盤勢。成員瀏覽雲端資料不需要管理員電腦保持開機。

長條圖：左端 −30%、中央 0%、右端 +30%；超出範圍長條封頂，右側顯示實際報酬率。金額均為新台幣。
