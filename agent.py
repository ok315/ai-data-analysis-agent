import os
import pandas as pd
from dotenv import load_dotenv
from groq import Groq

FORBIDDEN_PATTERNS = [
    "import os", "import sys", "import subprocess", "import shutil",
    "__import__", "open(", "exec(", "eval(", "os.", "sys.", "subprocess.",
    "shutil.", ".system(", "input(", "compile(",
]

def is_code_safe(code):
    lowered = code.lower()
    # pd.eval / df.eval are legitimate pandas methods, not the dangerous builtin eval()
    safe_to_remove = lowered.replace("pd.eval(", "").replace("df.eval(", "")
    for pattern in FORBIDDEN_PATTERNS:
        if pattern.lower() in safe_to_remove:
            return False, f"Generated code contains forbidden pattern: '{pattern}'"
    return True, None

load_dotenv()
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

df = pd.read_csv("expenses.csv")

def build_prompt(question, dataframe):
    columns_info = f"Columns: {list(dataframe.columns)}\n"
    sample_rows = f"First 3 rows:\n{dataframe.head(3).to_string()}"
    
    system_message = f"""You are a data analysis assistant. You answer questions about a dataframe called `df` by first planning, then writing pandas code.

{columns_info}
{sample_rows}

You must respond in EXACTLY this format, with both sections present:

PLAN:
- Write 2-4 short bullet points describing the steps needed to answer the question.

CODE:
- Python pandas code that follows your plan.
- The dataframe is already loaded as `df`, do not recreate it.
- Store your final answer in a variable called `result`.
- Do not include markdown formatting like ```python.
- Do not include any explanation in this section, only code.
"""
    return system_message

def is_clean_result(result):
    if isinstance(result, (pd.Series, pd.DataFrame)):
        return False, f"result is a {type(result).__name__}, expected a single value"
    if isinstance(result, (tuple, dict, list)):
        return False, f"result is a {type(result).__name__} containing multiple values, expected a single value"
    if result is None:
        return False, "result was never set"
    return True, None

def generate_code(question, error_context=None):
    system_message = build_prompt(question, df)
    
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": question}
    ]
    
    if error_context:
        messages.append({"role": "assistant", "content": error_context["previous_response"]})
        messages.append({"role": "user", "content": f"""Your code failed with this error:
{error_context["error"]}

Fix the code. Keep the same PLAN/CODE format. Make sure the code addresses the specific error above, while also preserving every other fix and requirement from earlier in this conversation. Do not reintroduce a mistake you already corrected previously."""})
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages
    )
    
    return response.choices[0].message.content

def parse_response(full_response):
    if "CODE:" not in full_response:
        raise ValueError("LLM did not return a CODE section")
    
    plan_part, code_part = full_response.split("CODE:")
    plan = plan_part.replace("PLAN:", "").strip()
    code = code_part.strip()
    return plan, code

def ask_agent_with_retry(question, max_retries=4):
    error_context = None
    seen_errors = []
    
    for attempt in range(1, max_retries + 1):
        print(f"\n--- Attempt {attempt} ---")
        
        full_response = generate_code(question, error_context)
        plan, code = parse_response(full_response)
        
        print("Plan:\n", plan)
        print("Generated code:\n", code)
        
        safe, safety_reason = is_code_safe(code)
        if not safe:
            print(f"Attempt {attempt} blocked (unsafe code): {safety_reason}")
            error_context = {
                "previous_response": full_response,
                "error": f"Your code was blocked for safety reasons: {safety_reason}. Rewrite the code using only pandas operations on the `df` dataframe — do not use file system access, system commands, or imports beyond what's already provided."
            }
            continue
        
        local_vars = {"df": df, "pd": pd}
        
        try:
            exec(code, local_vars)
            result = local_vars.get("result")
        except Exception as e:
            error_text = str(e)
            print(f"Attempt {attempt} failed (runtime error): {error_text}")
            
            is_repeat = any(error_text == past_error for past_error in seen_errors)
            seen_errors.append(error_text)
            
            if is_repeat:
                print("This is a REPEATED error — escalating message.")
                error_message = f"""You already encountered this EXACT error before in this conversation and your fix did not stick: {error_text}

This time, make sure your fix for this specific error is preserved even while fixing anything else. Do not regress on a previously-fixed issue."""
            else:
                error_message = f"Your code failed with this error: {error_text}"
            
            error_context = {
                "previous_response": full_response,
                "error": error_message
            }
            continue
        
        clean, reason = is_clean_result(result)
        if not clean:
            print(f"Attempt {attempt} failed (bad shape): {reason}")
            error_context = {
                "previous_response": full_response,
                "error": f"The code ran without crashing, but produced an invalid final answer: {reason}. The `result` variable must hold a single clean value (a number, string, or short value) that directly answers the question — not a Series, DataFrame, or tuple."
            }
            continue
        
        print(f"\nSuccess on attempt {attempt}")
        return result, plan, attempt
    
    raise RuntimeError(f"Agent failed after {max_retries} attempts. Errors seen: {seen_errors}")

if __name__ == "__main__":
    question = "what's the average monthly spending per category, and which month had the most categories exceeding their own average?"
    answer, plan, attempts_used = ask_agent_with_retry(question)
    print(f"\nFinal Answer: {answer}")
    print(f"Attempts needed: {attempts_used}")