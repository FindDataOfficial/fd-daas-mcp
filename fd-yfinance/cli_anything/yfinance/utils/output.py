import json
import sys

try:
    import pandas as pd
except ImportError:
    pd = None


def format_output(result, json_output=False):
    if pd is not None and isinstance(result, pd.DataFrame):
        if json_output:
            data = result.to_dict(orient="records")
            print(json.dumps(data, ensure_ascii=False, default=str))
        else:
            pd.set_option("display.max_columns", None)
            pd.set_option("display.max_rows", None)
            pd.set_option("display.width", None)
            pd.set_option("display.max_colwidth", 50)
            print(result.to_string(index=False))
    elif pd is not None and isinstance(result, pd.Series):
        if json_output:
            print(json.dumps(result.to_dict(), ensure_ascii=False, default=str))
        else:
            print(result.to_string())
    elif isinstance(result, (dict, list)):
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        print(str(result))
