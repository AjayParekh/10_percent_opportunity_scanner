# config.py
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_RAW = BASE_DIR / "data" / "raw"
DATA_IMPORTS = BASE_DIR / "data" / "imports"
DB_PATH = BASE_DIR / "database" / "scanner.db"

# 数据来源标识：TheAnnexure 是首选，缺失时不得静默回退
SOURCE_ANNEXURE = "TheAnnexure"
SOURCE_NSE = "NSE"
SOURCE_BSE = "BSE"
SOURCE_MANUAL = "manual_import"

# 请求限速（秒），遵守合理请求频率
REQUEST_DELAY = 2.5
REQUEST_TIMEOUT = 15

# 打分权重占位，等待你的项目规范确认后填入
OPPORTUNITY_WEIGHTS = {}  # 不自行发明公式，留空占位
ENTRY_WEIGHTS = {}
