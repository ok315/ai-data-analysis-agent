from agent import ask_agent_with_retry
import time
import re

EVAL_QUESTIONS = [
    {"question": "What is the total amount spent on Food?", "expected": 5350},
    {"question": "What is the total amount spent on Transport?", "expected": 1550},
    {"question": "What is the total amount spent on Entertainment?", "expected": 3500},
    {"question": "How many transactions are there in total?", "expected": 10},
    {"question": "Which category had the highest total spending?", "expected": "Food"},
    {"question": "What is the difference between the highest and lowest category spending?", "expected": 3800},
    {"question": "What is the average amount spent per transaction?", "expected": 1040.0},
    {"question": "What was the total spending in March 2024?", "expected": 4850},
    {"question": "Which month had the highest total spending?", "expected": "2024-03"},
    {"question": "What's the average monthly spending per category, and which month had the most categories exceeding their own average?", "expected": "2024-03"},
]

def values_match(actual, expected):
    try:
        return abs(float(actual) - float(expected)) < 0.01
    except (ValueError, TypeError):
        pass
    
    actual_str = str(actual).strip().lower()
    expected_str = str(expected).strip().lower()
    
    if actual_str == expected_str:
        return True
    
    # Handle month-format equivalence: "3" matches "2024-03"
    actual_month = re.search(r'(\d{1,2})$', actual_str.replace('-', ' '))
    expected_month = re.search(r'(\d{1,2})$', expected_str.replace('-', ' '))
    if actual_month and expected_month:
        return int(actual_month.group(1)) == int(expected_month.group(1))
    
    return False

def run_evaluation():
    results = []
    
    for item in EVAL_QUESTIONS:
        question = item["question"]
        expected = item["expected"]
        print(f"\n{'='*60}\nQuestion: {question}")
        
        start_time = time.time()
        try:
            answer, plan, attempts = ask_agent_with_retry(question)
            elapsed = round(time.time() - start_time, 2)
            correct = values_match(answer, expected)
            results.append({
                "question": question, "expected": expected, "actual": answer,
                "correct": correct, "attempts": attempts, "time_seconds": elapsed, "crashed": False
            })
            print(f"Got: {answer} | Expected: {expected} | Correct: {correct} | Attempts: {attempts} | Time: {elapsed}s")
        except Exception as e:
            elapsed = round(time.time() - start_time, 2)
            results.append({
                "question": question, "expected": expected, "actual": None,
                "correct": False, "attempts": None, "time_seconds": elapsed, "crashed": True, "error": str(e)
            })
            print(f"CRASHED: {e}")
    
    total = len(results)
    correct_count = sum(1 for r in results if r["correct"])
    crashed_count = sum(1 for r in results if r["crashed"])
    avg_attempts = sum(r["attempts"] for r in results if r["attempts"]) / max(1, (total - crashed_count))
    avg_time = sum(r["time_seconds"] for r in results) / total
    
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"Total questions: {total}")
    print(f"Correct: {correct_count}/{total} ({round(100*correct_count/total, 1)}%)")
    print(f"Crashed (never recovered): {crashed_count}/{total}")
    print(f"Average attempts (non-crashed): {round(avg_attempts, 2)}")
    print(f"Average response time: {round(avg_time, 2)}s")
    
    return results

if __name__ == "__main__":
    run_evaluation()