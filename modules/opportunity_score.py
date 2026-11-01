# modules/opportunity_score.py
"""
100 分 Opportunity Score 的计算入口。
权重和分段规则必须来自项目规范；在规范确认前，
本模块返回占位结果，不猜测任何公式。
"""
import pandas as pd
from config import OPPORTUNITY_WEIGHTS

def compute_opportunity_score(fundamentals: pd.DataFrame) -> pd.Series:
    if not OPPORTUNITY_WEIGHTS:
        return pd.Series([None] * len(fundamentals), index=fundamentals.index)
    # 按已批准的权重逐项计算（占位）
    raise NotImplementedError("等待项目规范确认 Opportunity Score 权重。")
