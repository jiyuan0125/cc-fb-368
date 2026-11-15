#!/usr/bin/env python3
"""Build registry.csv, mismatch.csv, summary.csv from settle packages.

Date authority: the manifest's settle_date is authoritative. It is written at
export time and stays consistent with footer generated_at (settle_date + 1 day)
and detail txn_date (settle_date - 1 day). The directory-name date is only a
packaging-time label and is not updated when a package is re-exported, so it is
ignored.
"""
import csv
import os
import sys

def parse_kv(path):
    kv = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and "=" in line:
                k, v = line.split("=", 1)
                kv[k.strip()] = v.strip()
    return kv

def amount_to_cents(s):
    s = s.strip()
    neg = s.startswith("-")
    if neg:
        s = s[1:]
    if "." in s:
        whole, frac = s.split(".", 1)
    else:
        whole, frac = s, ""
    frac = (frac + "00")[:2]
    cents = int(whole or "0") * 100 + int(frac)
    return -cents if neg else cents

def fmt_amount(cents):
    neg = cents < 0
    cents = abs(cents)
    return ("-" if neg else "") + f"{cents // 100}.{cents % 100:02d}"

def main(settle_root, out_dir):
    packages = []
    for channel in sorted(os.listdir(settle_root)):
        ch_dir = os.path.join(settle_root, channel)
        if not os.path.isdir(ch_dir):
            continue
        for date_dir in sorted(os.listdir(ch_dir)):
            pkg = os.path.join(ch_dir, date_dir)
            if not os.path.isdir(pkg):
                continue
            rel = os.path.relpath(pkg, settle_root)
            manifest = parse_kv(os.path.join(pkg, "manifest.txt"))
            footer = parse_kv(os.path.join(pkg, "footer.txt"))

            count = 0
            total_cents = 0
            with open(os.path.join(pkg, "detail.csv"), newline="",
                      encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    count += 1
                    total_cents += amount_to_cents(row["amount"])

            packages.append({
                "path": rel,
                "channel": manifest["channel"],
                "settle_date": manifest["settle_date"],
                "generated_at": footer["generated_at"],
                "declared_count": int(manifest["record_count"]),
                "declared_total_cents": amount_to_cents(manifest["total_amount"]),
                "actual_count": count,
                "actual_total_cents": total_cents,
            })

    packages.sort(key=lambda p: (p["channel"], p["settle_date"]))

    with open(os.path.join(out_dir, "registry.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["channel", "settle_date", "record_count", "total_amount",
                    "generated_at"])
        for p in packages:
            w.writerow([p["channel"], p["settle_date"], p["actual_count"],
                        fmt_amount(p["actual_total_cents"]), p["generated_at"]])

    mismatches = []
    for p in packages:
        if p["declared_count"] != p["actual_count"]:
            mismatches.append([p["path"], "record_count",
                               str(p["declared_count"]), str(p["actual_count"])])
        if p["declared_total_cents"] != p["actual_total_cents"]:
            mismatches.append([p["path"], "total_amount",
                               fmt_amount(p["declared_total_cents"]),
                               fmt_amount(p["actual_total_cents"])])
    mismatches.sort(key=lambda r: (r[0], r[1]))
    with open(os.path.join(out_dir, "mismatch.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["package_path", "item", "declared", "actual"])
        w.writerows(mismatches)

    summary = {}
    for p in packages:
        key = (p["channel"], p["settle_date"])
        c, t = summary.get(key, (0, 0))
        summary[key] = (c + p["actual_count"], t + p["actual_total_cents"])
    with open(os.path.join(out_dir, "summary.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["channel", "settle_date", "record_count", "total_amount"])
        for (channel, settle_date) in sorted(summary):
            c, t = summary[(channel, settle_date)]
            w.writerow([channel, settle_date, c, fmt_amount(t)])

if __name__ == "__main__":
    settle_root = sys.argv[1] if len(sys.argv) > 1 else "settle"
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "."
    main(settle_root, out_dir)
