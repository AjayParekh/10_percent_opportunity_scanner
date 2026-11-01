# scrapers/annexure_scraper.py
"""
TheAnnexure 数据入口。

自动抓取不可用时，本模块的唯一合法行为是：
1. 引导用户将导出的 CSV/Excel 放入 data/imports/；
2. 严格校验列名、报告期和字段完整性；
3. 写入 metric_facts 时 source 固定为 TheAnnexure。
不执行任何“从其他网站补值”的逻辑。
"""
import pandas as pd
from config import SOURCE_ANNEXURE
from modules.data_validation import validate_annexure_frame

def load_from_import(filepath: str) -> pd.DataFrame:
    df = pd.read_csv(filepath) if filepath.endswith(".csv") else pd.read_excel(filepath)
    validated, report = validate_annexure_frame(df)
    # report 中若存在缺失字段，后续写入 DB 时 quality_status 应为 'missing'
    return validated, report
