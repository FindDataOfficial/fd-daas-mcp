import sys
import importlib
import inspect


def call_akshare_function(func_name, params=None, proxy=None):
    """Call an AKShare function by name with key=value parameters.

    Args:
        func_name: AKShare function name (e.g., 'stock_zh_a_hist').
        params: Dict of parameter key=value pairs.
        proxy: Optional ProxyController instance. If provided, proxy
               env vars are applied before the call and restored after.

    Returns:
        The function's return value (usually a pandas DataFrame).
    """
    if params is None:
        params = {}

    # Apply proxy if provided
    if proxy is not None:
        proxy.apply()

    try:
        akshare = importlib.import_module("akshare")
    except ImportError:
        print("Error: akshare is not installed.")
        print("Install it with: micromamba run -n akshare-kit pip install akshare")
        sys.exit(1)
    func = getattr(akshare, func_name, None)
    if func is None:
        available = [x for x in dir(akshare) if not x.startswith("_")]
        print(f"Error: function '{func_name}' not found in akshare")
        print(f"Use 'cli-anything-akshare search <term>' to find functions")
        sys.exit(1)
    try:
        result = func(**params)
    except TypeError as e:
        sig = inspect.signature(func)
        param_hints = []
        for p_name, p_param in sig.parameters.items():
            default = ""
            if p_param.default is not inspect.Parameter.empty:
                default = f" (default: {p_param.default})"
            param_hints.append(f"  --{p_name}{default}")
        print(f"Error calling {func_name}: {e}")
        print(f"Required parameters:")
        for hint in param_hints:
            print(hint)
        sys.exit(1)
    except Exception as e:
        print(f"Error executing {func_name}: {e}")
        sys.exit(1)
    return result
