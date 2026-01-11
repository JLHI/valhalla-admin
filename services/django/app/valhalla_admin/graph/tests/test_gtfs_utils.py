import os
import tempfile
import shutil
from valhalla_admin.gtfs.utils import ensure_calendar_augmented


def write_csv(path, header, rows):
    import csv
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow(r)


def test_ensure_calendar_augmented_creates_calendar_from_dates():
    tmp = tempfile.mkdtemp()
    try:
        # Prepare calendar_dates with two dates for one service
        cal_dates = os.path.join(tmp, 'calendar_dates.txt')
        write_csv(
            cal_dates,
            ['service_id','date','exception_type'],
            [
                ['wknd','20250103','1'],
                ['wknd','20250104','1'],
            ]
        )
        # No calendar.txt initially
        msg = ensure_calendar_augmented(tmp)
        assert 'calendar.txt complété' in msg or 'synthétisé' in msg or 'complété' in msg
        # Verify calendar.txt exists
        cal_path = os.path.join(tmp, 'calendar.txt')
        assert os.path.exists(cal_path)
        # Basic content check
        with open(cal_path, 'r', encoding='utf-8') as f:
            content = f.read()
            assert 'service_id' in content and 'wknd' in content
    finally:
        shutil.rmtree(tmp)


def test_ensure_calendar_augmented_no_dates_info():
    tmp = tempfile.mkdtemp()
    try:
        # calendar_dates exists but no added entries
        cal_dates = os.path.join(tmp, 'calendar_dates.txt')
        write_csv(
            cal_dates,
            ['service_id','date','exception_type'],
            [
                ['wknd','20250103','2'],
            ]
        )
        msg = ensure_calendar_augmented(tmp)
        assert 'aucun exception_type=1' in msg
    finally:
        shutil.rmtree(tmp)
