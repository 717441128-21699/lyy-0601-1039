"""文件扫描模块 - 读取Excel/CSV员工材料清单"""
import os
import csv
from datetime import date, datetime
from typing import List, Dict, Optional, Tuple
import pandas as pd

from hr_cert_reminder.config.config import AppConfig
from hr_cert_reminder.common.models import EmployeeCert, ScanResult, PersistentState


class DateParser:
    """日期解析器 - 支持多种日期格式"""

    def __init__(self, formats: List[str]):
        self.formats = formats

    def parse(self, date_str: str) -> Optional[date]:
        """尝试用多种格式解析日期"""
        if not date_str or pd.isna(date_str):
            return None

        date_str = str(date_str).strip()
        if not date_str:
            return None

        for fmt in self.formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except (ValueError, TypeError):
                continue

        try:
            if isinstance(date_str, str) and len(date_str) >= 6:
                clean = ''.join(c for c in date_str if c.isdigit())
                if len(clean) == 8:
                    return datetime.strptime(clean, "%Y%m%d").date()
                elif len(clean) == 6:
                    return datetime.strptime(clean, "%y%m%d").date()
        except (ValueError, TypeError):
            pass

        try:
            ts = pd.to_datetime(date_str)
            if pd.notna(ts):
                return ts.date()
        except (ValueError, TypeError):
            pass

        return None


class FieldMapper:
    """字段映射器 - 根据配置自动匹配列名"""

    def __init__(self, field_mapping: Dict[str, List[str]]):
        self.field_mapping = field_mapping

    def map_columns(self, columns: List[str]) -> Dict[str, str]:
        """将实际列名映射到标准字段名"""
        mapping = {}
        lower_columns = {str(col).strip().lower(): col for col in columns}

        for std_field, aliases in self.field_mapping.items():
            for alias in aliases:
                alias_lower = alias.strip().lower()
                if alias_lower in lower_columns:
                    mapping[std_field] = lower_columns[alias_lower]
                    break

        return mapping

    def identify_missing_fields(self, mapping: Dict[str, str]) -> List[str]:
        """检查缺失的必填字段"""
        required = ["employee_name", "department", "cert_type", "expiry_date"]
        return [f for f in required if f not in mapping]


class MaterialScanner:
    """材料扫描器"""

    def __init__(self, config: AppConfig, state: Optional[PersistentState] = None):
        self.config = config
        self.state = state or PersistentState()
        self.date_parser = DateParser(config.date_formats)
        self.field_mapper = FieldMapper(config.field_mapping)

    def scan_directory(self, dir_path: Optional[str] = None) -> ScanResult:
        """扫描目录中的所有Excel和CSV文件"""
        scan_dir = dir_path or self.config.materials_dir
        scan_dir = os.path.abspath(scan_dir)

        result = ScanResult()

        if not os.path.exists(scan_dir):
            print(f"警告: 材料目录不存在: {scan_dir}")
            return result

        supported_extensions = ['.xlsx', '.xls', '.csv']
        files = []
        for ext in supported_extensions:
            files.extend([
                os.path.join(scan_dir, f)
                for f in os.listdir(scan_dir)
                if f.lower().endswith(ext) and not f.startswith('~$')
            ])

        result.total_files = len(files)
        print(f"找到 {len(files)} 个待扫描文件")

        for idx, file_path in enumerate(files, 1):
            print(f"\n[{idx}/{len(files)}] 正在扫描: {os.path.basename(file_path)}")
            file_result = self.scan_file(file_path)
            result.records.extend(file_result.records)
            result.invalid_records.extend(file_result.invalid_records)
            result.valid_records += file_result.valid_records

        for emp in result.records:
            self.state.apply_to(emp)

        return result

    def scan_file(self, file_path: str) -> ScanResult:
        """扫描单个文件"""
        result = ScanResult()
        result.total_files = 1

        try:
            if file_path.lower().endswith('.csv'):
                df = self._read_csv(file_path)
            else:
                df = self._read_excel(file_path)
        except Exception as e:
            result.invalid_records.append({
                "file": os.path.basename(file_path),
                "row": "N/A",
                "issue": f"文件读取失败: {str(e)}",
                "data": {}
            })
            return result

        if df.empty:
            result.invalid_records.append({
                "file": os.path.basename(file_path),
                "row": "N/A",
                "issue": "文件为空",
                "data": {}
            })
            return result

        col_mapping = self.field_mapper.map_columns(list(df.columns))
        missing_fields = self.field_mapper.identify_missing_fields(col_mapping)

        if missing_fields:
            print(f"  ⚠ 缺少字段: {', '.join(missing_fields)}")
            print(f"  检测到的列: {list(df.columns)}")
            print(f"  字段映射: {col_mapping}")

        for idx, row in df.iterrows():
            row_num = idx + 2
            emp, issues = self._parse_row(row, col_mapping, file_path)

            if issues:
                result.invalid_records.append({
                    "file": os.path.basename(file_path),
                    "row": row_num,
                    "issue": "; ".join(issues),
                    "data": {str(k): str(v) for k, v in row.to_dict().items() if pd.notna(v)}
                })
            elif emp:
                result.records.append(emp)
                result.valid_records += 1

        print(f"  ✓ 有效记录: {result.valid_records}, 需处理: {len(result.invalid_records)}")
        return result

    def _read_excel(self, file_path: str) -> pd.DataFrame:
        """读取Excel文件"""
        return pd.read_excel(file_path, dtype=str)

    def _read_csv(self, file_path: str) -> pd.DataFrame:
        """读取CSV文件，自动检测编码"""
        encodings = ['utf-8-sig', 'utf-8', 'gbk', 'gb2312']
        for enc in encodings:
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    sample = f.read(4096)
                try:
                    dialect = csv.Sniffer().sniff(sample)
                    return pd.read_csv(file_path, encoding=enc, dialect=dialect, dtype=str)
                except csv.Error:
                    return pd.read_csv(file_path, encoding=enc, dtype=str)
            except UnicodeDecodeError:
                continue
        return pd.read_csv(file_path, encoding='utf-8', dtype=str, errors='ignore')

    def _parse_row(
        self,
        row: pd.Series,
        col_mapping: Dict[str, str],
        file_path: str
    ) -> Tuple[Optional[EmployeeCert], List[str]]:
        """解析单行数据"""
        issues = []

        def get_value(field: str) -> str:
            if field in col_mapping:
                val = row.get(col_mapping[field], "")
                return "" if pd.isna(val) else str(val).strip()
            return ""

        employee_name = get_value("employee_name")
        department = get_value("department")
        cert_type = get_value("cert_type")
        raw_date = get_value("expiry_date")

        if not employee_name:
            issues.append("员工姓名为空")
        if not department:
            issues.append("部门为空")
        if not cert_type:
            issues.append("证照类型为空")

        if issues:
            return None, issues

        expiry_date = self.date_parser.parse(raw_date) if raw_date else None

        if not raw_date:
            issues.append("到期日期为空")
        elif expiry_date is None:
            issues.append(f"日期格式无法识别: '{raw_date}'")

        emp = EmployeeCert(
            employee_name=employee_name,
            department=department,
            cert_type=cert_type,
            expiry_date=expiry_date,
            raw_date_str=raw_date,
            file_path=file_path
        )

        return emp, issues

    def print_invalid_records(self, result: ScanResult) -> None:
        """打印需要手动处理的记录"""
        if not result.invalid_records:
            print("\n✓ 所有记录格式正确，无需手动处理")
            return

        print(f"\n{'='*60}")
        print(f"⚠  需要手动处理的记录 ({len(result.invalid_records)} 条)")
        print(f"{'='*60}")

        for idx, rec in enumerate(result.invalid_records, 1):
            print(f"\n{idx}. 文件: {rec['file']} | 行: {rec['row']}")
            print(f"   问题: {rec['issue']}")
            if rec['data']:
                data_str = " | ".join([f"{k}: {v}" for k, v in list(rec['data'].items())[:5]])
                print(f"   数据: {data_str}")

        print(f"\n{'='*60}")
