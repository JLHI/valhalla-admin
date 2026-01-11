import os
import csv
from datetime import datetime


def ensure_calendar_augmented(feed_dir: str):
    """
    Ensure calendar.txt covers dates present in calendar_dates.txt (exception_type=1).
    Returns a summary string of changes applied or an info message.
    """
    cal_path = os.path.join(feed_dir, "calendar.txt")
    cal_dates_path = os.path.join(feed_dir, "calendar_dates.txt")

    if not os.path.exists(cal_dates_path):
        return f"ℹ️ {os.path.basename(feed_dir)}: calendar_dates.txt absent → aucune augmentation de calendar.txt"

    # Collect added dates per service_id
    added = {}
    total_dates_rows = 0
    try:
        with open(cal_dates_path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                total_dates_rows += 1
                sid = (row.get("service_id") or "").strip()
                try:
                    exc = int(str(row.get("exception_type", "")).strip())
                except Exception:
                    exc = None
                dstr = (row.get("date") or "").strip()
                try:
                    d = datetime.strptime(dstr, "%Y%m%d").date()
                except Exception:
                    d = None
                if not sid or exc != 1 or not d:
                    continue
                added.setdefault(sid, []).append(d)
    except Exception:
        return f"ℹ️ {os.path.basename(feed_dir)}: lecture calendar_dates.txt impossible → aucune augmentation"

    if not added:
        return f"ℹ️ {os.path.basename(feed_dir)}: aucun exception_type=1 dans calendar_dates ({total_dates_rows} lignes)"

    header = [
        "service_id","monday","tuesday","wednesday","thursday",
        "friday","saturday","sunday","start_date","end_date"
    ]

    existing_rows = []
    by_sid = {}
    existing_ok = False
    if os.path.exists(cal_path):
        try:
            with open(cal_path, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.DictReader(f)
                cols = reader.fieldnames or []
                essential = {"service_id","start_date","end_date","monday","tuesday","wednesday","thursday","friday","saturday","sunday"}
                if set([c.lower() for c in cols]) >= essential:
                    for row in reader:
                        if not row.get("service_id"):
                            continue
                        existing_rows.append(row)
                    existing_ok = len(existing_rows) > 0
        except Exception:
            existing_ok = False

    if existing_ok:
        for r in existing_rows:
            sid = r.get("service_id", "").strip()
            if not sid or sid in by_sid:
                continue
            by_sid[sid] = r

    changed = False
    appended = 0
    extended = 0
    flags_updates = 0

    def _flags_from_dates(dates):
        wset = {d.weekday() for d in dates}
        return [
            1 if 0 in wset else 0,
            1 if 1 in wset else 0,
            1 if 2 in wset else 0,
            1 if 3 in wset else 0,
            1 if 4 in wset else 0,
            1 if 5 in wset else 0,
            1 if 6 in wset else 0,
        ]

    for sid, dates in added.items():
        mind = min(dates)
        maxd = max(dates)
        flags = _flags_from_dates(dates)
        if sid not in by_sid:
            row = {
                "service_id": sid,
                "monday": str(flags[0]),
                "tuesday": str(flags[1]),
                "wednesday": str(flags[2]),
                "thursday": str(flags[3]),
                "friday": str(flags[4]),
                "saturday": str(flags[5]),
                "sunday": str(flags[6]),
                "start_date": mind.strftime("%Y%m%d"),
                "end_date": maxd.strftime("%Y%m%d"),
            }
            existing_rows.append(row)
            by_sid[sid] = row
            changed = True
            appended += 1
        else:
            row = by_sid[sid]
            try:
                cur_start = datetime.strptime((row.get("start_date") or "").strip(), "%Y%m%d").date()
                cur_end = datetime.strptime((row.get("end_date") or "").strip(), "%Y%m%d").date()
            except Exception:
                cur_start, cur_end = mind, maxd
            new_start = min(cur_start, mind)
            new_end = max(cur_end, maxd)
            if new_start != cur_start or new_end != cur_end:
                row["start_date"] = new_start.strftime("%Y%m%d")
                row["end_date"] = new_end.strftime("%Y%m%d")
                changed = True
                extended += 1
            weekday_cols = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
            for i, col in enumerate(weekday_cols):
                try:
                    cur = int(str(row.get(col, "0")).strip() or "0")
                except Exception:
                    cur = 0
                new_val = 1 if (cur == 1 or flags[i] == 1) else 0
                if new_val != cur:
                    row[col] = str(new_val)
                    changed = True
                    flags_updates += 1

    if not existing_ok and existing_rows:
        changed = True

    if not changed:
        return f"ℹ️ {os.path.basename(feed_dir)}: calendar.txt inchangé (service_ids ajoutés={len(added)}, existants={len(by_sid)})"

    try:
        with open(cal_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=header)
            writer.writeheader()
            for r in existing_rows:
                writer.writerow({
                    "service_id": r.get("service_id", ""),
                    "monday": r.get("monday", "0"),
                    "tuesday": r.get("tuesday", "0"),
                    "wednesday": r.get("wednesday", "0"),
                    "thursday": r.get("thursday", "0"),
                    "friday": r.get("friday", "0"),
                    "saturday": r.get("saturday", "0"),
                    "sunday": r.get("sunday", "0"),
                    "start_date": r.get("start_date", ""),
                    "end_date": r.get("end_date", ""),
                })
        return (
            f"🧩 {os.path.basename(feed_dir)}: calendar.txt complété → "
            f"ajoutés={appended}, étendus={extended}, flags_modifiés={flags_updates}"
        )
    except Exception as e:
        return f"⚠️ Écriture calendar.txt impossible: {e}"
