"""
Runner for yfinance function calls.

Dispatches a registry command to a live yfinance call:
  - ticker_<method>: constructs yfinance.Ticker(symbol) and calls .<method>(**rest)
  - everything else: calls yfinance.<name>(**params) directly

Mirrors the akshare runner's error handling (clear messages, signature hints).
"""
from __future__ import annotations

import importlib
import inspect
import sys
from typing import Optional


def call_yfinance_function(func_name: str, params: Optional[dict] = None):
    """Call a yfinance function by registry command name.

    Args:
        func_name: Registry command (e.g. 'ticker_history', 'download').
        params: Dict of parameter key=value pairs. For ticker_* commands,
                'symbol' selects the Ticker; the rest are passed to the method.

    Returns:
        The function's return value (DataFrame, dict, Series, etc.).
    """
    if params is None:
        params = {}

    try:
        yfinance = importlib.import_module("yfinance")
    except ImportError:
        print("Error: yfinance is not installed.")
        print("Install it with: pip install yfinance")
        sys.exit(1)

    # Dispatch: ticker_<method> -> Ticker(symbol).<method>(**rest)
    if func_name.startswith("ticker_"):
        method_name = func_name[len("ticker_"):]
        symbol = params.pop("symbol", None)
        if symbol is None:
            print(f"Error: '{func_name}' requires a 'symbol' parameter")
            sys.exit(1)
        ticker = yfinance.Ticker(symbol)
        method = getattr(ticker, method_name, None)
        if method is None or not callable(method):
            print(f"Error: Ticker has no callable method '{method_name}'")
            sys.exit(1)
        target = method
        target_name = f"Ticker({symbol}).{method_name}"
    else:
        target = getattr(yfinance, func_name, None)
        if target is None or not callable(target):
            available = [
                x for x in dir(yfinance) if not x.startswith("_") and callable(getattr(yfinance, x))
            ]
            print(f"Error: function '{func_name}' not found in yfinance")
            print(f"Use 'cli-anything-yfinance search <term>' to find functions")
            print(f"Top-level yfinance callables include: {', '.join(available[:20])}")
            sys.exit(1)
        target_name = func_name

    try:
        result = target(**params)
    except TypeError as e:
        sig = inspect.signature(target)
        param_hints = []
        for p_name, p_param in sig.parameters.items():
            default = ""
            if p_param.default is not inspect.Parameter.empty:
                default = f" (default: {p_param.default})"
            param_hints.append(f"  --{p_name}{default}")
        print(f"Error calling {target_name}: {e}")
        print(f"Parameters:")
        for hint in param_hints:
            print(hint)
        sys.exit(1)
    except Exception as e:
        print(f"Error executing {target_name}: {e}")
        sys.exit(1)
    return result
