"""数据模型定义"""
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import Optional, List, Dict
import json
import os


@dataclass
class EmployeeCert:
    """员工证照信息"""
    employee_name: str
    department: str
    cert_type: str
    expiry_date: Optional[date] = None
    raw_date_str: str = ""
    is_resigned: bool = False
    manual_corrected_date: Optional[date] = None
    is_renewed: bool = False
    renewed_date: Optional[date] = None
    file_path: str = ""
    remarks: str = ""

    def to_dict(self) -> Dict:
        data = asdict(self)
        for key in ['expiry_date', 'manual_corrected_date', 'renewed_date']:
            if data[key]:
                data[key] = data[key].isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> 'EmployeeCert':
        for key in ['expiry_date', 'manual_corrected_date', 'renewed_date']:
            if data.get(key):
                data[key] = date.fromisoformat(data[key])
        return cls(**data)

    def get_effective_expiry(self) -> Optional[date]:
        """获取有效的到期日期（优先使用手动修正日期）"""
        return self.manual_corrected_date or self.expiry_date

    def needs_reminder(self) -> bool:
        """是否需要提醒"""
        if self.is_resigned or self.is_renewed:
            return False
        return self.get_effective_expiry() is not None

    def days_until_expiry(self, today: Optional[date] = None) -> Optional[int]:
        """计算距离到期的天数"""
        if today is None:
            today = date.today()
        effective_date = self.get_effective_expiry()
        if effective_date is None:
            return None
        return (effective_date - today).days


@dataclass
class ReminderRecord:
    """提醒记录"""
    employee: EmployeeCert
    days_until_expiry: int
    reminder_level: str  # 30天, 15天, 7天, 已逾期

    def to_dict(self) -> Dict:
        return {
            "employee": self.employee.to_dict(),
            "days_until_expiry": self.days_until_expiry,
            "reminder_level": self.reminder_level
        }


@dataclass
class PersistentState:
    """持久化状态 - 保存手动修正、离职、续办等信息"""
    resigned_employees: List[str] = field(default_factory=list)
    manual_corrections: Dict[str, date] = field(default_factory=dict)
    renewed_certs: Dict[str, date] = field(default_factory=dict)
    remarks: Dict[str, str] = field(default_factory=dict)

    @staticmethod
    def _get_key(emp: EmployeeCert) -> str:
        return f"{emp.employee_name}|{emp.cert_type}"

    def apply_to(self, emp: EmployeeCert) -> EmployeeCert:
        """将持久化状态应用到员工证照记录"""
        key = self._get_key(emp)

        if emp.employee_name in self.resigned_employees:
            emp.is_resigned = True

        if key in self.manual_corrections:
            emp.manual_corrected_date = self.manual_corrections[key]

        if key in self.renewed_certs:
            emp.is_renewed = True
            emp.renewed_date = self.renewed_certs[key]

        if key in self.remarks:
            emp.remarks = self.remarks[key]

        return emp

    def mark_resigned(self, employee_name: str) -> None:
        """标记已离职"""
        if employee_name not in self.resigned_employees:
            self.resigned_employees.append(employee_name)

    def unmark_resigned(self, employee_name: str) -> None:
        """取消离职标记"""
        if employee_name in self.resigned_employees:
            self.resigned_employees.remove(employee_name)

    def set_manual_correction(self, emp: EmployeeCert, new_date: date) -> None:
        """设置手动修正日期"""
        key = self._get_key(emp)
        self.manual_corrections[key] = new_date

    def clear_manual_correction(self, emp: EmployeeCert) -> None:
        """清除手动修正日期"""
        key = self._get_key(emp)
        if key in self.manual_corrections:
            del self.manual_corrections[key]

    def mark_renewed(self, emp: EmployeeCert, renewed_date: Optional[date] = None) -> None:
        """标记已续办"""
        key = self._get_key(emp)
        if renewed_date is None:
            renewed_date = date.today()
        self.renewed_certs[key] = renewed_date

    def unmark_renewed(self, emp: EmployeeCert) -> None:
        """取消续办标记"""
        key = self._get_key(emp)
        if key in self.renewed_certs:
            del self.renewed_certs[key]

    def set_remark(self, emp: EmployeeCert, remark: str) -> None:
        """设置备注"""
        key = self._get_key(emp)
        self.remarks[key] = remark

    def save(self, file_path: str) -> None:
        """保存到文件"""
        data = {
            "resigned_employees": self.resigned_employees,
            "manual_corrections": {k: v.isoformat() for k, v in self.manual_corrections.items()},
            "renewed_certs": {k: v.isoformat() for k, v in self.renewed_certs.items()},
            "remarks": self.remarks
        }
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, file_path: str) -> 'PersistentState':
        """从文件加载"""
        if not os.path.exists(file_path):
            return cls()
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            state = cls()
            state.resigned_employees = data.get("resigned_employees", [])
            state.manual_corrections = {
                k: date.fromisoformat(v)
                for k, v in data.get("manual_corrections", {}).items()
            }
            state.renewed_certs = {
                k: date.fromisoformat(v)
                for k, v in data.get("renewed_certs", {}).items()
            }
            state.remarks = data.get("remarks", {})
            return state
        except Exception:
            return cls()


@dataclass
class ScanResult:
    """扫描结果"""
    records: List[EmployeeCert] = field(default_factory=list)
    invalid_records: List[Dict] = field(default_factory=list)
    total_files: int = 0
    valid_records: int = 0

    def summary(self) -> str:
        return (f"共扫描 {self.total_files} 个文件，"
                f"有效记录 {self.valid_records} 条，"
                f"需手动处理 {len(self.invalid_records)} 条")
