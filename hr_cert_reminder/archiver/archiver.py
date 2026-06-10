"""归档模块 - 归档历史数据"""
import os
import shutil
import json
from datetime import date, datetime
from typing import List, Dict
import zipfile

from hr_cert_reminder.common.models import ReminderRecord


class Archiver:
    """归档器"""

    def __init__(self, archive_dir: str):
        self.archive_dir = os.path.abspath(archive_dir)
        os.makedirs(self.archive_dir, exist_ok=True)

    def archive_run(
        self,
        output_dir: str,
        reminders: Dict[str, List[ReminderRecord]],
        scan_result_summary: Dict,
        run_mode: str
    ) -> str:
        """归档本次运行结果"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"run_{timestamp}"
        archive_path = os.path.join(self.archive_dir, archive_name)
        os.makedirs(archive_path, exist_ok=True)

        if os.path.exists(output_dir):
            for item in os.listdir(output_dir):
                src = os.path.join(output_dir, item)
                dst = os.path.join(archive_path, item)
                if os.path.isdir(src):
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dst)

        summary = {
            "run_timestamp": timestamp,
            "run_date": date.today().isoformat(),
            "run_mode": run_mode,
            "scan_summary": scan_result_summary,
            "reminder_counts": {
                level: len(records) for level, records in reminders.items()
            },
            "total_reminders": sum(len(r) for r in reminders.values())
        }

        summary_path = os.path.join(archive_path, "run_summary.json")
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        reminder_data = []
        for level, records in reminders.items():
            for rec in records:
                reminder_data.append({
                    "level": level,
                    "days_until_expiry": rec.days_until_expiry,
                    "employee": rec.employee.to_dict()
                })

        data_path = os.path.join(archive_path, "reminder_data.json")
        with open(data_path, 'w', encoding='utf-8') as f:
            json.dump(reminder_data, f, ensure_ascii=False, indent=2)

        zip_path = archive_path + ".zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(archive_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, archive_path)
                    zipf.write(file_path, arcname)

        shutil.rmtree(archive_path)

        print(f"✓ 本次运行结果已归档 -> {os.path.relpath(zip_path)}")
        return zip_path

    def list_archives(self) -> List[str]:
        """列出所有归档文件"""
        archives = []
        for f in os.listdir(self.archive_dir):
            if f.endswith('.zip'):
                archives.append(os.path.join(self.archive_dir, f))
        return sorted(archives, reverse=True)

    def get_archive_summary(self, archive_path: str) -> Dict:
        """获取归档摘要"""
        with zipfile.ZipFile(archive_path, 'r') as zipf:
            with zipf.open('run_summary.json') as f:
                return json.load(f)

    def cleanup_old_archives(self, keep_days: int = 90) -> int:
        """清理指定天数前的归档"""
        import time
        now = time.time()
        cutoff = now - (keep_days * 86400)
        cleaned = 0

        for f in os.listdir(self.archive_dir):
            fpath = os.path.join(self.archive_dir, f)
            if f.endswith('.zip') and os.path.getmtime(fpath) < cutoff:
                os.remove(fpath)
                cleaned += 1

        if cleaned > 0:
            print(f"✓ 已清理 {cleaned} 个超过 {keep_days} 天的旧归档")
        return cleaned
