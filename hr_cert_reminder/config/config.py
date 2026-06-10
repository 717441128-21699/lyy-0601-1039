"""配置管理模块"""
import json
import os
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional


@dataclass
class Recipient:
    """接收人配置"""
    name: str
    email: str
    role: str = "部门负责人"
    departments: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'Recipient':
        return cls(**data)


@dataclass
class AppConfig:
    """应用配置"""
    materials_dir: str = "data/materials"
    output_dir: str = "data/output"
    archive_dir: str = "data/archive"
    state_file: str = "data/persistent_state.json"

    reminder_days: List[int] = field(default_factory=lambda: [30, 15, 7])

    field_mapping: Dict[str, List[str]] = field(default_factory=lambda: {
        "employee_name": ["姓名", "员工姓名", "name", "employee_name"],
        "department": ["部门", "所属部门", "department", "dept"],
        "cert_type": ["证照类型", "证件类型", "证书类型", "cert_type", "type"],
        "expiry_date": ["到期日期", "有效期至", "截止日期", "expiry_date", "expire_date", "valid_until"]
    })

    cert_types: Dict[str, str] = field(default_factory=lambda: {
        "健康证": "健康证",
        "资格证": "资格证书",
        "劳动合同": "劳动合同",
        "身份证": "身份证",
        "驾驶证": "驾驶证",
        "特种作业证": "特种作业操作证"
    })

    recipients: List[Recipient] = field(default_factory=list)

    date_formats: List[str] = field(default_factory=lambda: [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y.%m.%d",
        "%Y年%m月%d日",
        "%y-%m-%d",
        "%y/%m/%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%Y%m%d"
    ])

    def to_dict(self) -> Dict:
        data = asdict(self)
        data["recipients"] = [r.to_dict() for r in self.recipients]
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> 'AppConfig':
        recipients_data = data.get("recipients", [])
        recipients = [Recipient.from_dict(r) for r in recipients_data]
        config = cls()
        for key, value in data.items():
            if key != "recipients" and hasattr(config, key):
                setattr(config, key, value)
        config.recipients = recipients
        return config

    def save(self, file_path: str) -> None:
        """保存配置到文件"""
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, file_path: str) -> 'AppConfig':
        """从文件加载配置"""
        if not os.path.exists(file_path):
            config = cls()
            config.save(file_path)
            return config
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return cls.from_dict(data)
        except Exception as e:
            print(f"配置文件加载失败，使用默认配置: {e}")
            return cls()

    def get_recipients_for_department(self, department: str) -> List[Recipient]:
        """获取指定部门的接收人"""
        result = []
        for r in self.recipients:
            if not r.departments or department in r.departments:
                result.append(r)
        return result
