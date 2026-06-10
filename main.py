"""HR 员工证照到期提醒自动化工具 - 主程序入口"""
import argparse
import sys
import os
from datetime import date, datetime
from typing import List, Dict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hr_cert_reminder.config.config import AppConfig
from hr_cert_reminder.common.models import (
    EmployeeCert, ScanResult, PersistentState, ReminderRecord
)
from hr_cert_reminder.scanner.scanner import MaterialScanner
from hr_cert_reminder.reminder.reminder import ReminderGenerator, NotificationSender
from hr_cert_reminder.report.report import ReportGenerator
from hr_cert_reminder.archiver.archiver import Archiver


CONFIG_FILE = "config.json"


class HRCertReminderApp:
    """HR证照提醒应用主类"""

    def __init__(self, config_path: str = CONFIG_FILE):
        self.config = AppConfig.load(config_path)
        self.state = PersistentState.load(self.config.state_file)
        self.scanner = MaterialScanner(self.config, self.state)
        self.reminder_gen = ReminderGenerator(self.config)
        self.sender = NotificationSender(self.config)
        self.reporter = ReportGenerator(self.config.output_dir)
        self.archiver = Archiver(self.config.archive_dir)

        self.scan_result: ScanResult = None
        self.reminders: Dict[str, List[ReminderRecord]] = {}

    def run_check_only(self) -> None:
        """运行模式1: 只检查 - 扫描并显示结果，不生成文件"""
        print("\n" + "="*60)
        print("🔍  模式: 仅检查")
        print("="*60)

        self._do_scan()
        if not self.scan_result.records:
            return

        self._do_generate_reminders()
        self._print_reminder_summary()
        self._print_excluded_records()

    def run_generate_only(self) -> Dict[str, str]:
        """运行模式2: 生成文件 - 扫描并生成所有报表"""
        print("\n" + "="*60)
        print("📄  模式: 生成报表文件")
        print("="*60)

        self._do_scan()
        if not self.scan_result.records:
            return {}

        self._do_generate_reminders()
        self._print_reminder_summary()
        self._print_excluded_records()

        self._clear_output_dir()
        generated_files = self.reporter.generate_all_reports(
            self.reminders, self.reminder_gen
        )

        self._do_archive("generate_only")
        self._save_state()

        return generated_files

    def run_generate_and_send(self) -> Dict:
        """运行模式3: 生成并发送 - 生成报表并发送通知"""
        print("\n" + "="*60)
        print("📤  模式: 生成并发送提醒")
        print("="*60)

        self._do_scan()
        if not self.scan_result.records:
            return {}

        self._do_generate_reminders()
        self._print_reminder_summary()
        self._print_excluded_records()

        self._clear_output_dir()
        generated_files = self.reporter.generate_all_reports(
            self.reminders, self.reminder_gen
        )

        notifications = self.sender.build_notifications(
            self.reminders, self.reminder_gen
        )
        send_results = self.sender.send_notifications(notifications, dry_run=True)

        self._do_archive("generate_and_send")
        self._save_state()

        return {
            "generated_files": generated_files,
            "send_results": send_results
        }

    def run_interactive(self) -> None:
        """交互式管理模式"""
        self._do_scan()
        self._do_generate_reminders()

        while True:
            print("\n" + "="*60)
            print("⚙️  HR证照管理 - 交互模式")
            print("="*60)
            print("\n请选择操作:")
            print("  1. 查看提醒列表")
            print("  2. 标记已离职人员")
            print("  3. 取消离职标记")
            print("  4. 手动修正到期日期")
            print("  5. 清除日期修正")
            print("  6. 标记已续办")
            print("  7. 取消续办标记")
            print("  8. 添加备注")
            print("  9. 查看持久化状态")
            print(" 10. 查看需手动处理的记录")
            print(" 11. 保存并返回")
            print("  0. 放弃并退出")

            choice = input("\n请输入选项 (0-11): ").strip()

            if choice == "1":
                self._print_reminder_summary()
            elif choice == "2":
                self._interactive_mark_resigned()
            elif choice == "3":
                self._interactive_unmark_resigned()
            elif choice == "4":
                self._interactive_correct_date()
            elif choice == "5":
                self._interactive_clear_correction()
            elif choice == "6":
                self._interactive_mark_renewed()
            elif choice == "7":
                self._interactive_unmark_renewed()
            elif choice == "8":
                self._interactive_add_remark()
            elif choice == "9":
                self._print_persistent_state()
            elif choice == "10":
                self.scanner.print_invalid_records(self.scan_result)
            elif choice == "11":
                self._save_state()
                self._do_generate_reminders()
                break
            elif choice == "0":
                print("已放弃修改")
                break
            else:
                print("无效选项，请重新输入")

    def _do_scan(self) -> None:
        """执行扫描"""
        print(f"\n正在扫描材料目录: {os.path.abspath(self.config.materials_dir)}")
        self.scan_result = self.scanner.scan_directory()
        print(f"\n扫描完成: {self.scan_result.summary()}")

        if self.scan_result.invalid_records:
            self.scanner.print_invalid_records(self.scan_result)

    def _do_generate_reminders(self) -> None:
        """生成提醒"""
        self.reminders = self.reminder_gen.generate_reminders(self.scan_result.records)

    def _do_archive(self, run_mode: str) -> None:
        """执行归档"""
        scan_summary = {
            "total_files": self.scan_result.total_files,
            "valid_records": self.scan_result.valid_records,
            "invalid_records": len(self.scan_result.invalid_records)
        }
        self.archiver.archive_run(
            self.config.output_dir,
            self.reminders,
            scan_summary,
            run_mode
        )

    def _print_reminder_summary(self) -> None:
        """打印提醒摘要"""
        self.reminder_gen.print_summary(self.reminders)

    def _print_excluded_records(self) -> None:
        """打印被排除的记录"""
        excluded_resigned = [e for e in self.scan_result.records if e.is_resigned]
        excluded_renewed = [e for e in self.scan_result.records if e.is_renewed]
        excluded_no_date = [e for e in self.scan_result.records if e.get_effective_expiry() is None]

        any_excluded = excluded_resigned or excluded_renewed or excluded_no_date
        if not any_excluded:
            return

        print(f"\n{'='*60}")
        print("ℹ️  已排除的记录")
        print(f"{'='*60}")

        if excluded_resigned:
            print(f"\n• 已离职 ({len(excluded_resigned)}人):")
            for e in excluded_resigned:
                print(f"  - {e.employee_name} ({e.department}) - {e.cert_type}")

        if excluded_renewed:
            print(f"\n• 已续办 ({len(excluded_renewed)}人):")
            for e in excluded_renewed:
                renewed = e.renewed_date.strftime('%Y-%m-%d') if e.renewed_date else ''
                print(f"  - {e.employee_name} ({e.department}) - {e.cert_type} (续办日期: {renewed})")

        if excluded_no_date:
            print(f"\n• 无有效日期 ({len(excluded_no_date)}人):")
            for e in excluded_no_date:
                print(f"  - {e.employee_name} ({e.department}) - {e.cert_type} (原始: {e.raw_date_str})")

        print(f"\n{'='*60}\n")

    def _print_persistent_state(self) -> None:
        """打印持久化状态"""
        print(f"\n{'='*60}")
        print("💾  持久化状态")
        print(f"{'='*60}")

        print(f"\n已离职人员 ({len(self.state.resigned_employees)}人):")
        if self.state.resigned_employees:
            for name in self.state.resigned_employees:
                print(f"  - {name}")
        else:
            print("  (无)")

        print(f"\n手动日期修正 ({len(self.state.manual_corrections)}条):")
        if self.state.manual_corrections:
            for key, d in self.state.manual_corrections.items():
                name, cert = key.split('|')
                print(f"  - {name} - {cert}: {d.strftime('%Y-%m-%d')}")
        else:
            print("  (无)")

        print(f"\n已续办标记 ({len(self.state.renewed_certs)}条):")
        if self.state.renewed_certs:
            for key, d in self.state.renewed_certs.items():
                name, cert = key.split('|')
                print(f"  - {name} - {cert}: 续办于 {d.strftime('%Y-%m-%d')}")
        else:
            print("  (无)")

        print(f"\n备注 ({len(self.state.remarks)}条):")
        if self.state.remarks:
            for key, remark in self.state.remarks.items():
                name, cert = key.split('|')
                print(f"  - {name} - {cert}: {remark}")
        else:
            print("  (无)")

        print(f"\n{'='*60}\n")

    def _save_state(self) -> None:
        """保存状态"""
        self.state.save(self.config.state_file)
        print(f"\n✓ 状态已保存到: {os.path.relpath(self.config.state_file)}")

    def _clear_output_dir(self) -> None:
        """清空输出目录"""
        output_dir = os.path.abspath(self.config.output_dir)
        if os.path.exists(output_dir):
            for item in os.listdir(output_dir):
                item_path = os.path.join(output_dir, item)
                try:
                    if os.path.isdir(item_path):
                        import shutil
                        shutil.rmtree(item_path)
                    else:
                        os.remove(item_path)
                except Exception as e:
                    print(f"警告: 无法删除 {item_path}: {e}")

    def _select_employee(self, prompt: str, include_all: bool = False) -> EmployeeCert:
        """交互式选择员工"""
        records = self.scan_result.records
        if not records:
            print("没有可用的记录")
            return None

        print(f"\n{prompt}")
        for idx, emp in enumerate(records, 1):
            status = ""
            if emp.is_resigned:
                status = " [已离职]"
            if emp.is_renewed:
                status = " [已续办]"
            if emp.manual_corrected_date:
                status += " [日期已修正]"
            expiry = emp.get_effective_expiry()
            expiry_str = expiry.strftime('%Y-%m-%d') if expiry else f"无效({emp.raw_date_str})"
            print(f"  {idx:2d}. {emp.employee_name} - {emp.department} - {emp.cert_type} - {expiry_str}{status}")

        while True:
            choice = input("\n请输入序号 (0取消): ").strip()
            if choice == "0":
                return None
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(records):
                    return records[idx]
            except ValueError:
                pass
            print("无效输入，请重新选择")

    def _interactive_mark_resigned(self) -> None:
        """交互: 标记离职"""
        emp = self._select_employee("选择要标记为已离职的员工:")
        if emp:
            self.state.mark_resigned(emp.employee_name)
            self.state.apply_to(emp)
            print(f"✓ 已标记 {emp.employee_name} 为已离职")

    def _interactive_unmark_resigned(self) -> None:
        """交互: 取消离职"""
        if not self.state.resigned_employees:
            print("当前没有已离职人员")
            return

        print("\n已离职人员:")
        for idx, name in enumerate(self.state.resigned_employees, 1):
            print(f"  {idx}. {name}")

        choice = input("\n选择要取消离职标记的序号 (0取消): ").strip()
        if choice == "0":
            return
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(self.state.resigned_employees):
                name = self.state.resigned_employees[idx]
                self.state.unmark_resigned(name)
                for emp in self.scan_result.records:
                    if emp.employee_name == name:
                        emp.is_resigned = False
                print(f"✓ 已取消 {name} 的离职标记")
        except ValueError:
            print("无效输入")

    def _interactive_correct_date(self) -> None:
        """交互: 修正日期"""
        emp = self._select_employee("选择要修正日期的记录:")
        if not emp:
            return

        while True:
            new_date_str = input(f"\n请输入新的到期日期 (YYYY-MM-DD)，原始: {emp.raw_date_str}: ").strip()
            if not new_date_str:
                return
            try:
                new_date = datetime.strptime(new_date_str, "%Y-%m-%d").date()
                self.state.set_manual_correction(emp, new_date)
                self.state.apply_to(emp)
                print(f"✓ 已将 {emp.employee_name} 的 {emp.cert_type} 到期日期修正为 {new_date_str}")
                break
            except ValueError:
                print("日期格式无效，请使用 YYYY-MM-DD 格式")

    def _interactive_clear_correction(self) -> None:
        """交互: 清除日期修正"""
        corrected = [e for e in self.scan_result.records if e.manual_corrected_date]
        if not corrected:
            print("当前没有已修正日期的记录")
            return

        print("\n已修正日期的记录:")
        for idx, emp in enumerate(corrected, 1):
            print(f"  {idx}. {emp.employee_name} - {emp.cert_type}: 修正为 {emp.manual_corrected_date.strftime('%Y-%m-%d')}")

        choice = input("\n选择要清除修正的序号 (0取消): ").strip()
        if choice == "0":
            return
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(corrected):
                emp = corrected[idx]
                self.state.clear_manual_correction(emp)
                emp.manual_corrected_date = None
                print(f"✓ 已清除 {emp.employee_name} 的日期修正")
        except ValueError:
            print("无效输入")

    def _interactive_mark_renewed(self) -> None:
        """交互: 标记续办"""
        emp = self._select_employee("选择要标记为已续办的记录:")
        if not emp:
            return

        while True:
            date_str = input(f"\n请输入续办日期 (YYYY-MM-DD，回车使用今天): ").strip()
            if not date_str:
                renewed_date = date.today()
                break
            try:
                renewed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                break
            except ValueError:
                print("日期格式无效，请使用 YYYY-MM-DD 格式")

        self.state.mark_renewed(emp, renewed_date)
        self.state.apply_to(emp)
        print(f"✓ 已标记 {emp.employee_name} 的 {emp.cert_type} 已续办 ({renewed_date.strftime('%Y-%m-%d')})")

    def _interactive_unmark_renewed(self) -> None:
        """交互: 取消续办标记"""
        renewed = [e for e in self.scan_result.records if e.is_renewed]
        if not renewed:
            print("当前没有已续办的记录")
            return

        print("\n已续办的记录:")
        for idx, emp in enumerate(renewed, 1):
            renewed_str = emp.renewed_date.strftime('%Y-%m-%d') if emp.renewed_date else ''
            print(f"  {idx}. {emp.employee_name} - {emp.cert_type} (续办: {renewed_str})")

        choice = input("\n选择要取消续办标记的序号 (0取消): ").strip()
        if choice == "0":
            return
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(renewed):
                emp = renewed[idx]
                self.state.unmark_renewed(emp)
                emp.is_renewed = False
                emp.renewed_date = None
                print(f"✓ 已取消 {emp.employee_name} 的续办标记")
        except ValueError:
            print("无效输入")

    def _interactive_add_remark(self) -> None:
        """交互: 添加备注"""
        emp = self._select_employee("选择要添加备注的记录:")
        if not emp:
            return

        remark = input(f"\n当前备注: {emp.remarks}\n请输入新备注: ").strip()
        self.state.set_remark(emp, remark)
        emp.remarks = remark
        print(f"✓ 已更新备注")


def print_banner():
    """打印欢迎横幅"""
    print("\n" + "="*60)
    print("  HR 员工证照到期提醒自动化工具 v1.0")
    print("=" * 60)
    print(f"  今天日期: {date.today().strftime('%Y年%m月%d日')}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="HR 员工证照到期提醒自动化工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
运行模式说明:
  check     仅扫描检查，显示结果不生成文件
  generate  扫描并生成所有报表文件到输出目录
  send      扫描、生成报表，并模拟发送通知给负责人
  manage    交互式管理模式，可标记离职、修正日期、标记续办等

示例:
  python main.py check              # 只检查
  python main.py generate           # 生成报表
  python main.py send               # 生成并发送
  python main.py manage             # 交互管理
  python main.py generate --config custom_config.json
        """
    )

    parser.add_argument(
        "mode",
        nargs="?",
        default="check",
        choices=["check", "generate", "send", "manage"],
        help="运行模式 (默认: check)"
    )

    parser.add_argument(
        "--config",
        default=CONFIG_FILE,
        help=f"配置文件路径 (默认: {CONFIG_FILE})"
    )

    parser.add_argument(
        "--no-archive",
        action="store_true",
        help="不归档本次运行结果"
    )

    args = parser.parse_args()

    print_banner()

    try:
        app = HRCertReminderApp(args.config)
    except Exception as e:
        print(f"\n❌ 初始化失败: {e}")
        sys.exit(1)

    try:
        if args.mode == "check":
            app.run_check_only()

        elif args.mode == "generate":
            files = app.run_generate_only()
            if files:
                print(f"\n✓ 共生成 {len(files)} 个文件:")
                for name, path in files.items():
                    print(f"  - {name}: {os.path.relpath(path)}")

        elif args.mode == "send":
            results = app.run_generate_and_send()
            if results:
                files = results.get("generated_files", {})
                sends = results.get("send_results", [])
                print(f"\n✓ 共生成 {len(files)} 个文件，发送 {len(sends)} 条通知")

        elif args.mode == "manage":
            app.run_interactive()

    except KeyboardInterrupt:
        print("\n\n用户中断操作")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 运行出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\n" + "="*60)
    print("✓ 运行完成")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
