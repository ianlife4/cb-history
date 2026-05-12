# cb-history

> 台股 CB(轉/交換公司債)**掛牌期間最高/最低價** 鏡像備份 + 公開查詢站。

資料來源:[cb168.netlify.app](https://cb168.netlify.app/) 公開 xlsx
線上站:<https://ianlife4.github.io/cb-history/>
GHA 排程:每天 01:00 UTC(09:00 台灣)

---

## 為什麼有這個 repo

[cb168.netlify.app](https://cb168.netlify.app/) 把 2200+ 檔台股 CB 的「掛牌期間最高/最低價」做成查詢站,但只有當下快照、沒有版本歷史。

本 repo 每天自動鏡像一次,並把資料 commit 到 git — git log 就是版本歷史,可以追溯任何一天的狀態變化。

順手做的兩件事:
1. **修補原檔已知亂碼** —— `81114` 在 cb168 原檔顯示為 `立�皏|`(U+FFFD 替代字元),已查證為「**立碁四**」(8111 立碁第 4 次無擔保 CB,2026/04/13 董事會發行)。
2. **公開乾淨資料** —— 同時輸出 JSON / CSV / 原始 xlsx,方便程式或試算表使用。

## 檔案結構

```
cb-history/
├── data/
│   ├── output.xlsx          ← cb168 原始備份(byte-for-byte)
│   ├── cb_data.json         ← 清洗版,含 metadata(updated_at / fixes_applied)
│   └── cb_data.csv          ← UTF-8 BOM,Excel 雙擊即開
├── scripts/
│   └── fetch.py             ← 下載 + 修補亂碼 + 輸出 3 種格式
├── .github/workflows/
│   └── daily-fetch.yml      ← GHA 排程,idempotent(資料沒變不 commit)
└── index.html               ← 前端 SPA(單檔,直接讀 data/cb_data.json)
```

## 資料 schema (cb_data.json)

```jsonc
{
  "updated_at": "2026-05-12 15:31:35 UTC",
  "source": "https://cb168.netlify.app/output.xlsx",
  "count": 2276,
  "fixes_applied": [
    { "code": 81114, "original": "立�皏|", "fixed": "立碁四" }
  ],
  "items": [
    { "代號": 11011, "名稱": "台泥一永", "掛牌最高": 108.1, "掛牌最低": 94.4 },
    /* … */
  ]
}
```

| 欄位 | 型別 | 說明 |
|---|---|---|
| `代號` | int | CB 代號,5–6 位數,前 4 碼為母股代號、最後 1–2 碼為期別 |
| `名稱` | string | CB 簡稱(如「台泥一永」、「立碁四」) |
| `掛牌最高` | float | 整個掛牌期間的最高成交價 |
| `掛牌最低` | float | 整個掛牌期間的最低成交價 |

⚠️ 部分 CB 的價格欄位為 `0`,代表尚未掛牌或資料缺漏 —— 前端預設過濾掉。

## 本機開發

```bash
# 抓一次資料
pip install openpyxl
python scripts/fetch.py

# 預覽前端
python -m http.server 8000
# → http://localhost:8000/
```

## 部署

- **資料更新**:GHA 每天自動跑,有變動才 commit + push。手動觸發:Repo → Actions → "Daily CB168 Fetch" → Run workflow。
- **前端**:GitHub Pages(Settings → Pages → `main` / `(root)`)。
- **Worker 整合**:已在 [stock-dash](https://github.com/ianlife4/stock-dash)(私有)整合為 `/cb-history/` tab。

## 修補規則

新發現的亂碼或錯誤命名,加進 `scripts/fetch.py` 的 `KNOWN_FIXES` dict:

```python
KNOWN_FIXES: dict[int, str] = {
    81114: "立碁四",
}
```

## 授權

資料本身屬 cb168.netlify.app 收集者;本 repo 僅做鏡像 + 修補,程式碼採 MIT。
