"""track7 — Python training port for the NFL model suite.

Faithful retrains of the NFL models sdv-py uses as R-converted artifacts:
``xpass`` (dropback), ``fd`` (go-for-it gain), ``two_pt`` (2-pt conversion),
``fg`` (field-goal make probability, re-trained from a GAM as XGBoost), and the
``punt`` empirical landing distribution. Each is validated against the converted
R oracle (the parity gate).
"""
from __future__ import annotations
