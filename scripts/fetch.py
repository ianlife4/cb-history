#!/usr/bin/env python3
"""
從 cb168.netlify.app 抓取 CB 掛牌歷史最高/最低價,輸出 xlsx + json + csv。

- 每天由 GitHub Actions schedule 觸發
- 用 git diff 判斷有變動才 commit(workflow 端做)
- 修補原檔已知亂碼(KNOWN_FIXES)
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import openpyxl

URL = "https://cb168.netlify.app/output.xlsx"
USER_AGENT = "cb-history-mirror/1.0 (+https://github.com/ianlife4/cb-history)"

# 原檔已知亂碼修補: cb168 的 xlsx 在這些代號的「名稱」欄寫入了 U+FFFD,
# 經查證後對應到正確中文名稱。新發現的亂碼補進這個 dict 即可。
KNOWN_FIXES: dict[int, str] = {
    81114: "立碁四",  # 8111 立碁第 4 次無擔保 CB,原檔顯示為 "立�皏|"
}

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def download_xlsx(dest: Path) -> None:
    print(f"[fetch] GET {URL}")
    req = urllib.request.Request(URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp, open(dest, "wb") as f:
        f.write(resp.read())
    print(f"[fetch] wrote {dest} ({dest.stat().st_size} bytes)")


def parse_xlsx(path: Path) -> tuple[list[str], list[dict]]:
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise RuntimeError("xlsx is empty")
    header = [str(c) if c is not None else "" for c in rows[0]]
    expected = ["代號", "名稱", "掛牌最高", "掛牌最低"]
    if header != expected:
        raise RuntimeError(f"header mismatch: got {header}, expected {expected}")

    items: list[dict] = []
    fixes_applied: list[dict] = []
    for r in rows[1:]:
        code, name, hi, lo = r
        if code is None:
            continue
        if isinstance(code, int) and code in KNOWN_FIXES:
            fixes_applied.append({"code": code, "original": name, "fixed": KNOWN_FIXES[code]})
            name = KNOWN_FIXES[code]
        items.append({
            "代號": code,
            "名稱": name,
            "掛牌最高": hi,
            "掛牌最低": lo,
        })
    print(f"[parse] {len(items)} rows, {len(fixes_applied)} fixes applied")
    return header, items, fixes_applied  # type: ignore[return-value]


def write_outputs(header: list[str], items: list[dict], fixes_applied: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # JSON — NO timestamp inside; idempotent: same data → same bytes.
    # newline="\n" 是必要的:沒有它,在 Windows 上跑會寫出 CRLF,而 repo 存的是 LF
    # → git 會把整個 2,300 行的檔案報成「已修改」,製造一個純換行的假 diff,
    #   真正的資料變動會被埋在裡面看不出來。
    json_path = DATA_DIR / "cb_data.json"
    payload = {
        "source": URL,
        "count": len(items),
        "fixes_applied": fixes_applied,
        "items": items,
    }
    with open(json_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print(f"[write] {json_path}")

    # 資料指紋 + 真正的變動時間 —— 前端拿這個當「資料新鮮度」,不要再用 HTTP Last-Modified。
    #
    # 為什麼不能用 Last-Modified:實測 GitHub Pages 對 index.html 與 data/cb_data.json
    # 回的 Last-Modified **完全相同**(都是站台部署時間,不是檔案修改時間)。
    # 所以只要改個版面 push 一次,頁面就會宣稱「資料更新於今天」,但 items 其實是舊的
    # —— 一個會說謊的權威訊號,比沒有還糟。
    #
    # 這個檔只有在 items 的指紋真的變了才會被重寫,所以完全保留原本
    # 「資料沒變 → 同樣的 bytes → 沒有 commit」的 idempotent 設計。
    fingerprint = hashlib.sha256(
        json.dumps(items, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    meta_path = DATA_DIR / "last_change.json"
    prev_fp = None
    if meta_path.exists():
        try:
            prev_fp = json.loads(meta_path.read_text(encoding="utf-8")).get("fingerprint")
        except Exception:
            prev_fp = None
    if prev_fp != fingerprint:
        meta = {
            "fingerprint": fingerprint,
            "changed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "count": len(items),
        }
        with open(meta_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(meta, f, ensure_ascii=False, indent=1)
        print(f"[write] {meta_path} (資料有變動)")
    else:
        print(f"[skip]  {meta_path} (資料未變動,維持原時間)")

    # CSV (UTF-8 BOM, Excel-friendly)
    csv_path = DATA_DIR / "cb_data.csv"
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for d in items:
            w.writerow([d["代號"], d["名稱"], d["掛牌最高"], d["掛牌最低"]])
    print(f"[write] {csv_path}")


def main() -> int:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        xlsx_path = DATA_DIR / "output.xlsx"
        download_xlsx(xlsx_path)
        header, items, fixes_applied = parse_xlsx(xlsx_path)
        write_outputs(header, items, fixes_applied)
        print(f"[done] OK")
        return 0
    except Exception as e:
        print(f"[error] {type(e).__name__}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
