try:
    from langchain_core.runnables import RunnableSerializable
    print("RunnableSerializable: OK")
except Exception as e:
    print(f"RunnableSerializable: {e}")

try:
    from langchain_core.runnables.base import Runnable
    print("Runnable: OK")
except Exception as e:
    print(f"Runnable: {e}")

try:
    from langchain_core.callbacks.manager import CallbackManager
    print("CallbackManager: OK")
except Exception as e:
    print(f"CallbackManager: {e}")

try:
    from langchain_core.callbacks.base import BaseCallbackHandler
    print("BaseCallbackHandler: OK")
except Exception as e:
    print(f"BaseCallbackHandler: {e}")

try:
    from langchain_core.prompts import ChatPromptTemplate
    print("ChatPromptTemplate: OK")
except Exception as e:
    print(f"ChatPromptTemplate: {e}")

try:
    from langchain_core.tools import tool
    print("tool decorator: OK")
except Exception as e:
    print(f"tool decorator: {e}")

try:
    from langchain_core.utils.function_calling import convert_to_openai_function
    print("convert_to_openai_function: OK")
except Exception as e:
    print(f"convert_to_openai_function: {e}")

print("\n--- Checking langchain_community ---")
try:
    from langchain_community.agent_toolkits import create_openai_tools_agent
    print("create_openai_tools_agent: OK")
except Exception as e:
    print(f"create_openai_tools_agent: {e}")

try:
    from langchain_community.tools import Tool
    print("Tool: OK")
except Exception as e:
    print(f"Tool: {e}")
