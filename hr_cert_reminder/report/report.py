"""报表生成模块 - 生成个人提醒、部门汇总、逾期清单"""
import os
from datetime import date
from typing import List, Dict, Optional
import pandas as pd

from hr_cert_reminder.common.models import ReminderRecord, EmployeeCert
from hr_cert_reminder.reminder.reminder import ReminderGenerator


class ReportGenerator:
    """报表生成器"""

    def __init__(self, output_dir: str):
        self.output_dir = os.path.abspath(output_dir)
        os.makedirs(self.output_dir, exist_ok=True)

    def _get_date_suffix(self) -> str:
        """获取日期后缀"""
        return date.today().strftime("%Y%m%d")

    def generate_all_reports(
        self,
        reminders: Dict[str, List[ReminderRecord]],
        reminder_gen: ReminderGenerator
    ) -> Dict[str, str]:
        """生成所有报表"""
        generated_files = {}

        generated_files.update(self.generate_personal_reminders(reminders, reminder_gen))
        generated_files.update(self.generate_department_summary(reminders, reminder_gen))
        generated_files.update(self.generate_overdue_list(reminders))
        generated_files.update(self.generate_full_excel(reminders, reminder_gen))

        return generated_files

    def generate_personal_reminders(
        self,
        reminders: Dict[str, List[ReminderRecord]],
        reminder_gen: ReminderGenerator
    ) -> Dict[str, str]:
        """生成个人提醒文本"""
        date_suffix = self._get_date_suffix()
        personal_dir = os.path.join(self.output_dir, f"个人提醒_{date_suffix}")
        os.makedirs(personal_dir, exist_ok=True)

        all_records = []
        for records in reminders.values():
            all_records.extend(records)

        generated = {}

        for record in all_records:
            emp = record.employee
            file_name = f"{emp.employee_name}_{emp.cert_type}_提醒_{date_suffix}.txt"
            file_path = os.path.join(personal_dir, file_name)

            content = self._build_personal_reminder(record)

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            generated[f"个人提醒/{emp.employee_name}"] = file_path

        index_file = os.path.join(personal_dir, f"个人提醒汇总_{date_suffix}.txt")
        with open(index_file, 'w', encoding='utf-8') as f:
            f.write(f"证照到期个人提醒汇总 - {date.today().strftime('%Y年%m月%d日')}\n")
            f.write(f"{'='*60}\n\n")
            for record in all_records:
                emp = record.employee
                days = record.days_until_expiry
                days_str = f"已逾期{-days}天" if days < 0 else f"还有{days}天"
                f.write(f"• {emp.employee_name} ({emp.department}) - {emp.cert_type} - {days_str}\n")

        generated["个人提醒汇总"] = index_file
        print(f"✓ 已生成 {len(all_records)} 份个人提醒文件 -> {os.path.relpath(personal_dir)}")

        return generated

    def generate_department_summary(
        self,
        reminders: Dict[str, List[ReminderRecord]],
        reminder_gen: ReminderGenerator
    ) -> Dict[str, str]:
        """生成部门汇总表"""
        date_suffix = self._get_date_suffix()
        file_name = f"部门汇总表_{date_suffix}.xlsx"
        file_path = os.path.join(self.output_dir, file_name)

        by_dept = reminder_gen.group_by_department(reminders)

        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            for dept in sorted(by_dept.keys()):
                dept_reminders = by_dept[dept]
                rows = []

                for level in reminder_gen.LEVEL_ORDER:
                    if level in dept_reminders:
                        for record in dept_reminders[level]:
                            emp = record.employee
                            days = record.days_until_expiry
                            expiry_date = emp.get_effective_expiry()
                            rows.append({
                                "提醒级别": level,
                                "员工姓名": emp.employee_name,
                                "部门": emp.department,
                                "证照类型": emp.cert_type,
                                "到期日期": expiry_date.strftime("%Y-%m-%d") if expiry_date else "",
                                "剩余天数": f"已逾期{-days}" if days < 0 else days,
                                "是否已修正日期": "是" if emp.manual_corrected_date else "否",
                                "原始日期": emp.raw_date_str,
                                "备注": emp.remarks
                            })

                if rows:
                    df = pd.DataFrame(rows)
                    sheet_name = dept[:31] if len(dept) <= 31 else dept[:28] + "..."
                    df.to_excel(writer, sheet_name=sheet_name, index=False)

            summary_rows = []
            for dept in sorted(by_dept.keys()):
                dept_reminders = by_dept[dept]
                total = sum(len(r) for r in dept_reminders.values())
                row = {"部门": dept, "总计": total}
                for level in reminder_gen.LEVEL_ORDER:
                    row[level] = len(dept_reminders.get(level, []))
                summary_rows.append(row)

            if summary_rows:
                df_summary = pd.DataFrame(summary_rows)
                df_summary.to_excel(writer, sheet_name="部门统计汇总", index=False)

        print(f"✓ 已生成部门汇总表 -> {os.path.relpath(file_path)}")
        return {"部门汇总表": file_path}

    def generate_overdue_list(
        self,
        reminders: Dict[str, List[ReminderRecord]]
    ) -> Dict[str, str]:
        """生成逾期清单"""
        date_suffix = self._get_date_suffix()
        file_name = f"逾期清单_{date_suffix}.xlsx"
        file_path = os.path.join(self.output_dir, file_name)

        overdue_records = reminders.get(ReminderGenerator.LEVEL_OVERDUE, [])

        if not overdue_records:
            print("ℹ 当前没有逾期记录，跳过生成逾期清单")
            return {}

        rows = []
        for record in sorted(overdue_records, key=lambda r: r.days_until_expiry):
            emp = record.employee
            days_overdue = -record.days_until_expiry
            expiry_date = emp.get_effective_expiry()
            rows.append({
                "逾期天数": days_overdue,
                "员工姓名": emp.employee_name,
                "部门": emp.department,
                "证照类型": emp.cert_type,
                "到期日期": expiry_date.strftime("%Y-%m-%d") if expiry_date else "",
                "原始日期": emp.raw_date_str,
                "是否已修正日期": "是" if emp.manual_corrected_date else "否",
                "备注": emp.remarks
            })

        df = pd.DataFrame(rows)

        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name="逾期清单", index=False)

            summary = {
                "总逾期人数": [len(overdue_records)],
                "逾期30天以上": [sum(1 for r in overdue_records if -r.days_until_expiry > 30)],
                "逾期15-30天": [sum(1 for r in overdue_records if 15 <= -r.days_until_expiry <= 30)],
                "逾期15天以内": [sum(1 for r in overdue_records if -r.days_until_expiry < 15)]
            }
            df_summary = pd.DataFrame(summary)
            df_summary.to_excel(writer, sheet_name="逾期统计", index=False)

        print(f"✓ 已生成逾期清单 ({len(overdue_records)}条) -> {os.path.relpath(file_path)}")
        return {"逾期清单": file_path}

    def generate_full_excel(
        self,
        reminders: Dict[str, List[ReminderRecord]],
        reminder_gen: ReminderGenerator
    ) -> Dict[str, str]:
        """生成完整的提醒清单Excel"""
        date_suffix = self._get_date_suffix()
        file_name = f"证照到期提醒清单_{date_suffix}.xlsx"
        file_path = os.path.join(self.output_dir, file_name)

        all_records = []
        for level in reminder_gen.LEVEL_ORDER:
            if level in reminders:
                for record in reminders[level]:
                    all_records.append((level, record))

        if not all_records:
            return {}

        rows = []
        for level, record in all_records:
            emp = record.employee
            days = record.days_until_expiry
            expiry_date = emp.get_effective_expiry()
            rows.append({
                "提醒级别": level,
                "员工姓名": emp.employee_name,
                "部门": emp.department,
                "证照类型": emp.cert_type,
                "到期日期": expiry_date.strftime("%Y-%m-%d") if expiry_date else "",
                "剩余天数": f"已逾期{-days}" if days < 0 else days,
                "是否离职": "是" if emp.is_resigned else "否",
                "是否已续办": "是" if emp.is_renewed else "否",
                "是否已修正日期": "是" if emp.manual_corrected_date else "否",
                "原始日期": emp.raw_date_str,
                "数据来源": os.path.basename(emp.file_path),
                "备注": emp.remarks
            })

        df = pd.DataFrame(rows)

        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name="全部提醒", index=False)

            summary_data = []
            for level in reminder_gen.LEVEL_ORDER:
                count = len(reminders.get(level, []))
                if count > 0:
                    summary_data.append({"提醒级别": level, "人数": count})

            total = sum(len(r) for r in reminders.values())
            summary_data.append({"提醒级别": "总计", "人数": total})

            df_summary = pd.DataFrame(summary_data)
            df_summary.to_excel(writer, sheet_name="提醒统计", index=False)

        print(f"✓ 已生成完整提醒清单 -> {os.path.relpath(file_path)}")
        return {"完整提醒清单": file_path}

    def _build_personal_reminder(self, record: ReminderRecord) -> str:
        """构建个人提醒文本"""
        emp = record.employee
        days = record.days_until_expiry
        expiry_date = emp.get_effective_expiry()

        if days < 0:
            urgency = "⚠ 紧急 - 已逾期"
            days_desc = f"已逾期 {-days} 天"
        elif days <= 7:
            urgency = "🔴 紧急"
            days_desc = f"还有 {days} 天到期"
        elif days <= 15:
            urgency = "🟠 重要"
            days_desc = f"还有 {days} 天到期"
        else:
            urgency = "🟡 提醒"
            days_desc = f"还有 {days} 天到期"

        lines = [
            "=" * 50,
            f"{emp.cert_type}到期提醒",
            "=" * 50,
            "",
            f"员工姓名: {emp.employee_name}",
            f"所属部门: {emp.department}",
            f"证照类型: {emp.cert_type}",
            f"到期日期: {expiry_date.strftime('%Y年%m月%d日') if expiry_date else '未知'}",
            f"状态: {urgency} ({days_desc})",
            ""
        ]

        if emp.manual_corrected_date:
            lines.append("注: 此日期已由HR手动修正")

        lines.extend([
            "",
            "-" * 50,
            "请及时办理续期手续，以免影响正常工作。",
            "如有疑问，请联系HR部门。",
            "",
            f"生成时间: {date.today().strftime('%Y年%m月%d日')}",
            "=" * 50
        ])

        return '\n'.join(lines)
