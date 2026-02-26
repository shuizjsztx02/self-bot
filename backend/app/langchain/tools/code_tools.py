from langchain_core.tools import tool
from pydantic import BaseModel, Field
import sys
from io import StringIO


class CodeInput(BaseModel):
    code: str = Field(description="要执行的Python代码")
    timeout: int = Field(default=30, description="超时时间（秒）")


@tool(args_schema=CodeInput)
def execute_code(code: str, timeout: int = 30) -> str:
    """执行Python代码并返回结果"""
    try:
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        
        local_vars = {}
        exec(code, {"__builtins__": __builtins__}, local_vars)
        
        output = sys.stdout.getvalue()
        sys.stdout = old_stdout
        
        if output:
            return output
        elif "result" in local_vars:
            return str(local_vars["result"])
        else:
            return "执行成功，无输出"
    except Exception as e:
        if sys.stdout != old_stdout:
            sys.stdout = old_stdout
        return f"执行错误: {str(e)}"
