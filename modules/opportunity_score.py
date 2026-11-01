# modules/opportunity_score.py
"""
Calculation entry point for the 100-point Opportunity Score.
Weights and tiered rules must come from project specifications.
Prior to specification approval, this module returns placeholder results and does not guess any formulas.
"""
import pandas as pd
from config import OPPORTUNITY_WEIGHTS

def compute_opportunity_score(fundamentals: pd.DataFrame) -> pd.Series:
    if not OPPORTUNITY_WEIGHTS:
        return pd.Series([None] * len(fundamentals), index=fundamentals.index)
    # Calculate based on approved weights (Placeholder)
    raise NotImplementedError("Waiting for project specification confirmation on Opportunity Score weights.")
