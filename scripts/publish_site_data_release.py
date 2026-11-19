"""發布完整 JSON 副本；只讀匯出檔，不修改資料庫或既有網站。"""
import argparse
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
TAG = "site-data"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def prepare(data_dir, output_dir):
    data_dir, output_dir = Path(data_dir), Path(output_dir)
    index = read_json(data_dir / "index.json")
    stocks = index["stocks"]
    markets = ("tw", "us")
    counts = {m: sum(s.get("m") == m for s in stocks.values()) for m in markets}
    if not all(counts.values()) or index["total_records"] <= 0:
        raise ValueError("Both markets must contain stocks and records")
    dates = index["market_dates"]  # 既有網站發布步驟完成資料庫驗證後寫入
    for m in markets:
        date.fromisoformat(dates[m])
    months = index["months"]
    if not months or any(not re.fullmatch(r"\d{4}-\d{2}", m) for m in months):
        raise ValueError("Invalid or empty month index")
    result_counts = dict.fromkeys(markets, 0)
    for month in months:
        rows = read_json(data_dir / "months" / (month + ".json"))
        if not isinstance(rows, list) or not rows:
            raise ValueError("Empty month: " + month)
        for row in rows:
            market = stocks[row["id"]]["m"]
            if market in result_counts and row.get("lc") not in ("missing", "expired"):
                result_counts[market] += 1
    if not all(result_counts.values()):
        raise ValueError("Both markets must contain screening results")
    indicators = sorted((data_dir / "indicators").glob("*.json"))
    if not indicators:
        raise ValueError("Missing indicators")
    indicator_counts = dict.fromkeys(markets, 0)
    for path in indicators:
        for day, entries in read_json(path).items():
            for sid, values in entries.items():
                market = stocks.get(sid, {}).get("m")
                if market in indicator_counts and values:
                    indicator_counts[market] += 1
    if not all(indicator_counts.values()):
        raise ValueError("Both markets must contain indicators")
    # 完整資料夾一起打包；禁止連結與非 JSON 意外混入憑證或資料庫。
    files = sorted(p for p in data_dir.rglob("*") if p.is_file())
    for path in data_dir.rglob("*"):
        if path.is_symlink():
            raise ValueError("Symlinks are not allowed")
    for path in files:
        if path.suffix != ".json":
            raise ValueError("Unexpected non-JSON file: " + path.name)
        read_json(path)
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / "site-data.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for path in files:
            tar.add(path, arcname="data/" + path.relative_to(data_dir).as_posix())
    # 上傳前核對整包成員與原始位元組。
    with tarfile.open(archive, "r:gz") as tar:
        if len(tar.getmembers()) != len(files):
            raise ValueError("Archive file count mismatch")
        for path in files:
            member = "data/" + path.relative_to(data_dir).as_posix()
            if tar.extractfile(member).read() != path.read_bytes():
                raise ValueError("Archive content mismatch")
    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "tw_last_date": dates["tw"],
        "us_last_date": dates["us"],
        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "size": archive.stat().st_size,
    }
    manifest = output_dir / "site-data.json"
    manifest.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return archive, manifest, metadata


def publish(archive, manifest):
    existing = subprocess.run(["gh", "release", "view", TAG], capture_output=True)
    if existing.returncode:
        subprocess.run(["gh", "release", "create", TAG, "--prerelease", "--title", "Site JSON data",
                        "--notes", "完整選股 JSON 副本；讀取端須以 site-data.json 的 SHA-256 驗證資料包。"], check=True)
    # 必須分開執行；壓縮檔失敗就不更新就緒訊號。
    subprocess.run(["gh", "release", "upload", TAG, str(archive), "--clobber"], check=True)
    subprocess.run(["gh", "release", "upload", TAG, str(manifest), "--clobber"], check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=ROOT / "site" / "data")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "release-output")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    archive, manifest, metadata = prepare(args.data_dir, args.output_dir)
    if not args.prepare_only:
        publish(archive, manifest)
    print(json.dumps(metadata, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
