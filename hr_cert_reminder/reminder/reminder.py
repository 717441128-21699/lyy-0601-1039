"""提醒生成模块 - 按提醒阈值分组，生成提醒名单"""
from datetime import date
from typing import List, Dict, Optional
from collections import defaultdict

from hr_cert_reminder.config.config import AppConfig, Recipient
from hr_cert_reminder.common.models import EmployeeCert, ReminderRecord


class ReminderGenerator:
    """提醒生成器"""

    LEVEL_OVERDUE = "已逾期"
    LEVEL_7_DAYS = "7天"
    LEVEL_15_DAYS = "15天"
    LEVEL_30_DAYS = "30天"

    LEVEL_ORDER = [LEVEL_OVERDUE, LEVEL_7_DAYS, LEVEL_15_DAYS, LEVEL_30_DAYS]

    def __init__(self, config: AppConfig):
        self.config = config
        self.reminder_days = sorted(config.reminder_days)

    def generate_reminders(
        self,
        employees: List[EmployeeCert],
        today: Optional[date] = None
    ) -> Dict[str, List[ReminderRecord]]:
        """生成提醒名单，按提醒级别分组"""
        if today is None:
            today = date.today()

        grouped: Dict[str, List[ReminderRecord]] = defaultdict(list)

        for emp in employees:
            if not emp.needs_reminder():
                continue

            days = emp.days_until_expiry(today)
            if days is None:
                continue

            level = self._get_reminder_level(days)
            if level:
                record = ReminderRecord(
                    employee=emp,
                    days_until_expiry=days,
                    reminder_level=level
                )
                grouped[level].append(record)

        for level in grouped:
            grouped[level].sort(key=lambda r: (r.days_until_expiry, r.employee.department))

        return dict(grouped)

    def _get_reminder_level(self, days: int) -> Optional[str]:
        """根据剩余天数确定提醒级别"""
        if days < 0:
            return self.LEVEL_OVERDUE
        for threshold in self.reminder_days:
            if days <= threshold:
                return f"{threshold}天"
        return None

    def get_sorted_levels(self, grouped: Dict[str, List[ReminderRecord]]) -> List[str]:
        """获取排序后的提醒级别列表"""
        return [level for level in self.LEVEL_ORDER if level in grouped]

    def group_by_department(
        self,
        reminders: Dict[str, List[ReminderRecord]]
    ) -> Dict[str, Dict[str, List[ReminderRecord]]]:
        """将提醒按部门分组"""
        by_dept: Dict[str, Dict[str, List[ReminderRecord]]] = defaultdict(
            lambda: defaultdict(list)
        )

        for level, records in reminders.items():
            for record in records:
                dept = record.employee.department or "未知部门"
                by_dept[dept][level].append(record)

        return dict(by_dept)

    def print_summary(self, reminders: Dict[str, List[ReminderRecord]]) -> None:
        """打印提醒汇总"""
        print(f"\n{'='*60}")
        print("📋  证照到期提醒汇总")
        print(f"{'='*60}")

        total = sum(len(records) for records in reminders.values())
        if total == 0:
            print("\n✓ 当前没有需要提醒的证照到期记录")
            print(f"{'='*60}\n")
            return

        sorted_levels = self.get_sorted_levels(reminders)
        for level in sorted_levels:
            records = reminders[level]
            icon = "🔴" if level == self.LEVEL_OVERDUE else "🟠" if level == self.LEVEL_7_DAYS else "🟡"
            display_level = level if level == self.LEVEL_OVERDUE else f"{level}到期"
            print(f"\n{icon} 【{display_level}】 - {len(records)} 人")
            print(f"{'-'*60}")
            for rec in records:
                emp = rec.employee
                days_str = f"已逾期{-rec.days_until_expiry}天" if rec.days_until_expiry < 0 else f"还有{rec.days_until_expiry}天"
                mark = ""
                if emp.manual_corrected_date:
                    mark = " [日期已修正]"
                elif emp.remarks:
                    mark = f" [{emp.remarks}]"
                print(f"  • {emp.employee_name} ({emp.department}) - {emp.cert_type} - {days_str}{mark}")

        print(f"\n{'='*60}")
        print(f"总计: {total} 条提醒记录")
        print(f"{'='*60}\n")


class NotificationSender:
    """通知发送器（模拟发送）"""

    def __init__(self, config: AppConfig):
        self.config = config

    def build_notifications(
        self,
        reminders: Dict[str, List[ReminderRecord]],
        reminder_gen: ReminderGenerator
    ) -> List[Dict]:
        """构建待发送的通知列表"""
        notifications = []

        hr_recipients = [r for r in self.config.recipients if not r.departments]

        if hr_recipients:
            notifications.append({
                "recipients": hr_recipients,
                "scope": "全公司汇总",
                "reminders": reminders,
                "message": self._build_hr_message(reminders, reminder_gen)
            })

        by_dept = reminder_gen.group_by_department(reminders)
        for dept, dept_reminders in by_dept.items():
            dept_recipients = self.config.get_recipients_for_department(dept)
            dept_specific = [r for r in dept_recipients if r.departments]
            if dept_specific and dept_reminders:
                notifications.append({
                    "recipients": dept_specific,
                    "scope": f"{dept}部门",
                    "reminders": dept_reminders,
                    "message": self._build_dept_message(dept, dept_reminders, reminder_gen)
                })

        return notifications

    def send_notifications(
        self,
        notifications: List[Dict],
        dry_run: bool = True
    ) -> List[Dict]:
        """发送通知（模拟）"""
        results = []

        print(f"\n{'='*60}")
        print("📤 发送提醒通知")
        print(f"{'='*60}\n")

        for idx, notification in enumerate(notifications, 1):
            recipients = notification["recipients"]
            scope = notification["scope"]

            print(f"[{idx}] 发送范围: {scope}")
            print(f"    接收人:")
            for r in recipients:
                dept_note = f" (负责: {', '.join(r.departments)})" if r.departments else " (全公司)"
                print(f"      • {r.name} <{r.email}> - {r.role}{dept_note}")

            print(f"\n    通知内容:")
            for line in notification["message"].split('\n')[:10]:
                if line.strip():
                    print(f"      {line}")

            success = not dry_run or True
            status = "✓ 模拟发送成功" if dry_run else "✓ 已发送"

            print(f"\n    {status}\n")

            results.append({
                "scope": scope,
                "recipients": [r.to_dict() for r in recipients],
                "sent": True,
                "dry_run": dry_run
            })

        if not notifications:
            print("  没有需要发送的通知\n")

        print(f"{'='*60}\n")
        return results

    def _build_hr_message(
        self,
        reminders: Dict[str, List[ReminderRecord]],
        reminder_gen: ReminderGenerator
    ) -> str:
        """构建HR汇总消息"""
        total = sum(len(r) for r in reminders.values())
        lines = [
            f"【证照到期提醒 - 全公司汇总】",
            f"生成时间: {date.today().strftime('%Y年%m月%d日')}",
            f"共计: {total} 条记录",
            ""
        ]

        sorted_levels = reminder_gen.get_sorted_levels(reminders)
        for level in sorted_levels:
            records = reminders[level]
            display_level = level if level == ReminderGenerator.LEVEL_OVERDUE else f"{level}到期"
            lines.append(f"## {display_level} ({len(records)}人)")
            for rec in records:
                emp = rec.employee
                days = rec.days_until_expiry
                days_str = f"逾期{-days}天" if days < 0 else f"{days}天"
                lines.append(f"  • {emp.department} - {emp.employee_name} - {emp.cert_type} ({days_str})")
            lines.append("")

        return '\n'.join(lines)

    def _build_dept_message(
        self,
        department: str,
        reminders: Dict[str, List[ReminderRecord]],
        reminder_gen: ReminderGenerator
    ) -> str:
        """构建部门消息"""
        total = sum(len(r) for r in reminders.values())
        lines = [
            f"【证照到期提醒 - {department}】",
            f"生成时间: {date.today().strftime('%Y年%m月%d日')}",
            f"共计: {total} 条记录",
            ""
        ]

        sorted_levels = reminder_gen.get_sorted_levels(reminders)
        for level in sorted_levels:
            records = reminders[level]
            display_level = level if level == ReminderGenerator.LEVEL_OVERDUE else f"{level}到期"
            lines.append(f"## {display_level} ({len(records)}人)")
            for rec in records:
                emp = rec.employee
                days = rec.days_until_expiry
                days_str = f"逾期{-days}天" if days < 0 else f"{days}天"
                lines.append(f"  • {emp.employee_name} - {emp.cert_type} ({days_str})")
            lines.append("")

        lines.append("请及时提醒相关员工办理续期手续。")
        return '\n'.join(lines)
