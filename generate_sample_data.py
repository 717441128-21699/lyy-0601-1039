"""生成示例员工材料数据"""
import os
import pandas as pd
from datetime import date, timedelta


def generate_sample_data():
    """生成示例数据"""
    today = date.today()

    data = [
        {
            "姓名": "张三",
            "部门": "技术部",
            "证照类型": "健康证",
            "到期日期": (today + timedelta(days=5)).strftime("%Y-%m-%d")
        },
        {
            "姓名": "张三",
            "部门": "技术部",
            "证照类型": "资格证",
            "到期日期": (today + timedelta(days=25)).strftime("%Y/%m/%d")
        },
        {
            "姓名": "李四",
            "部门": "运营部",
            "证照类型": "劳动合同",
            "到期日期": (today + timedelta(days=12)).strftime("%Y.%m.%d")
        },
        {
            "姓名": "李四",
            "部门": "运营部",
            "证照类型": "健康证",
            "到期日期": (today + timedelta(days=-15)).strftime("%Y年%m月%d日")
        },
        {
            "姓名": "王五",
            "部门": "市场部",
            "证照类型": "健康证",
            "到期日期": (today + timedelta(days=45)).strftime("%y-%m-%d")
        },
        {
            "姓名": "王五",
            "部门": "市场部",
            "证照类型": "驾驶证",
            "到期日期": (today + timedelta(days=-40)).strftime("%Y%m%d")
        },
        {
            "姓名": "赵六",
            "部门": "行政部",
            "证照类型": "健康证",
            "到期日期": (today + timedelta(days=3)).strftime("%m/%d/%Y")
        },
        {
            "姓名": "赵六",
            "部门": "行政部",
            "证照类型": "资格证",
            "到期日期": (today + timedelta(days=18)).strftime("%d/%m/%Y")
        },
        {
            "姓名": "钱七",
            "部门": "财务部",
            "证照类型": "劳动合同",
            "到期日期": (today + timedelta(days=60)).strftime("%Y-%m-%d")
        },
        {
            "姓名": "钱七",
            "部门": "财务部",
            "证照类型": "健康证",
            "到期日期": (today + timedelta(days=-5)).strftime("%Y/%m/%d")
        },
        {
            "姓名": "孙八",
            "部门": "研发部",
            "证照类型": "特种作业证",
            "到期日期": (today + timedelta(days=8)).strftime("%Y.%m.%d")
        },
        {
            "姓名": "孙八",
            "部门": "研发部",
            "证照类型": "健康证",
            "到期日期": "2026-13-01"
        },
        {
            "姓名": "周九",
            "部门": "技术部",
            "证照类型": "健康证",
            "到期日期": "无效日期格式"
        },
        {
            "姓名": "周九",
            "部门": "技术部",
            "证照类型": "资格证",
            "到期日期": (today + timedelta(days=20)).strftime("%Y-%m-%d")
        },
        {
            "姓名": "吴十",
            "部门": "运营部",
            "证照类型": "健康证",
            "到期日期": ""
        },
        {
            "姓名": "吴十",
            "部门": "运营部",
            "证照类型": "劳动合同",
            "到期日期": (today + timedelta(days=28)).strftime("%Y年%m月%d日")
        },
        {
            "姓名": "",
            "部门": "技术部",
            "证照类型": "健康证",
            "到期日期": (today + timedelta(days=10)).strftime("%Y-%m-%d")
        },
        {
            "姓名": "郑十一",
            "部门": "",
            "证照类型": "健康证",
            "到期日期": (today + timedelta(days=10)).strftime("%Y-%m-%d")
        },
        {
            "姓名": "郑十一",
            "部门": "行政部",
            "证照类型": "",
            "到期日期": (today + timedelta(days=10)).strftime("%Y-%m-%d")
        },
        {
            "姓名": "王十二",
            "部门": "研发部",
            "证照类型": "健康证",
            "到期日期": (today + timedelta(days=-3)).strftime("%Y-%m-%d")
        },
    ]

    materials_dir = "data/materials"
    os.makedirs(materials_dir, exist_ok=True)

    df = pd.DataFrame(data)

    excel_path = os.path.join(materials_dir, "员工证照清单.xlsx")
    df.to_excel(excel_path, index=False)
    print(f"✓ 已生成 Excel 文件: {excel_path}")

    csv_path = os.path.join(materials_dir, "员工证照清单_补充.csv")
    additional_data = [
        {
            "员工姓名": "陈十三",
            "所属部门": "市场部",
            "证件类型": "健康证",
            "有效期至": (today + timedelta(days=7)).strftime("%Y-%m-%d")
        },
        {
            "员工姓名": "陈十三",
            "所属部门": "市场部",
            "证件类型": "资格证",
            "有效期至": (today + timedelta(days=-25)).strftime("%Y-%m-%d")
        },
        {
            "员工姓名": "褚十四",
            "所属部门": "技术部",
            "证件类型": "劳动合同",
            "有效期至": (today + timedelta(days=35)).strftime("%Y/%m/%d")
        },
        {
            "员工姓名": "褚十四",
            "所属部门": "技术部",
            "证件类型": "特种作业证",
            "有效期至": (today + timedelta(days=14)).strftime("%Y.%m.%d")
        },
        {
            "员工姓名": "卫十五",
            "所属部门": "财务部",
            "证件类型": "健康证",
            "有效期至": (today + timedelta(days=-60)).strftime("%Y年%m月%d日")
        },
    ]
    df2 = pd.DataFrame(additional_data)
    df2.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"✓ 已生成 CSV 文件: {csv_path}")

    print(f"\n共生成 {len(df) + len(df2)} 条记录")
    print(f"  - 正常日期: {sum(1 for d in data if d['到期日期'] and '无效' not in d['到期日期'] and '13' not in d['到期日期'] and d['姓名'] and d['部门'] and d['证照类型'])} 条")
    print(f"  - 日期格式问题: 2 条")
    print(f"  - 空值/空字段: 4 条")
    print(f"  - 已逾期: {sum(1 for d in data + additional_data if '-' in str(d.get('到期日期', '')) and '无效' not in str(d.get('到期日期', '')))} 条")


if __name__ == "__main__":
    generate_sample_data()
