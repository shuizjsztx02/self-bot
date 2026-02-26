from langchain_core.tools import tool
from pydantic import BaseModel, Field
from datetime import datetime
import json
import math


class CalculatorInput(BaseModel):
    expression: str = Field(description="数学表达式，如 '2 + 3 * 4' 或 'sqrt(16)'")


class TimeInput(BaseModel):
    format: str = Field(default="%Y-%m-%d %H:%M:%S", description="时间格式")


class JsonInput(BaseModel):
    action: str = Field(description="操作类型: parse, format, get")
    json_string: str = Field(description="JSON字符串")
    path: str = Field(default="", description="字段路径(用于get操作)")


@tool(args_schema=CalculatorInput)
def calculator(expression: str) -> str:
    """执行数学计算表达式，支持基本运算和常用数学函数"""
    try:
        allowed_names = {
            "abs": abs, "round": round, "min": min, "max": max,
            "sum": sum, "pow": pow, "len": len,
        }
        for name in dir(math):
            if not name.startswith("_"):
                allowed_names[name] = getattr(math, name)
        
        result = eval(expression, {"__builtins__": {}}, allowed_names)
        return str(result)
    except Exception as e:
        return f"计算错误: {str(e)}"


@tool(args_schema=TimeInput)
def current_time(format: str = "%Y-%m-%d %H:%M:%S") -> str:
    """获取当前日期和时间"""
    try:
        return datetime.now().strftime(format)
    except Exception as e:
        return f"格式错误: {str(e)}"


@tool(args_schema=JsonInput)
def json_parser(action: str, json_string: str, path: str = "") -> str:
    """解析、格式化或操作JSON数据"""
    try:
        data = json.loads(json_string)
        
        if action in ["parse", "format"]:
            return json.dumps(data, indent=2, ensure_ascii=False)
        elif action == "get":
            if not path:
                return "错误: 需要提供path参数"
            
            keys = path.split(".")
            result = data
            for key in keys:
                if key.isdigit():
                    result = result[int(key)]
                else:
                    result = result[key]
            
            if isinstance(result, (dict, list)):
                return json.dumps(result, indent=2, ensure_ascii=False)
            return str(result)
        else:
            return f"未知操作: {action}"
    except json.JSONDecodeError as e:
        return f"JSON解析错误: {str(e)}"
    except (KeyError, IndexError) as e:
        return f"路径错误: {str(e)}"
    except Exception as e:
        return f"操作错误: {str(e)}"
