#!/usr/bin/env python3
"""
從 cb168.netlify.app 抓取 CB 掛牌歷史最高/最低價,輸出 xlsx + json + csv。

- 每天由 GitHub Actions schedule 觸發
- 用 git diff 判斷有變動才 commit(workflow 端做)
- 修補原檔已知亂碼(KNOWN_FIXES)
"""
from __future__ import annotations

import csv
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

    # JSON
    json_path = DATA_DIR / "cb_data.json"
    payload = {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "source": URL,
        "count": len(items),
        "fixes_applied": fixes_applied,
        "items": items,
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print(f"[write] {json_path}")

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
