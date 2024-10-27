import os
import sys
import time
import argparse
from typing import Dict, Callable

# Add the parent directory to sys.path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from dotenv import load_dotenv
load_dotenv('.env')

from individual_evals.google_jobs import run_google_jobs_eval
from individual_evals.wikipedia import run_wikipedia_eval
from individual_evals.github_commits import run_github_commits_eval
from individual_evals.homedepot import run_homedepot_eval
from individual_evals.partners import run_partners_eval

def run(eval_name: str) -> Dict:
    """Run a specific eval by name and return its results."""
    evals: Dict[str, Callable] = {
        "Google Jobs": run_google_jobs_eval,
        "Wikipedia": run_wikipedia_eval,
        "GitHub Commits": run_github_commits_eval,
        "Home Depot": run_homedepot_eval,
        "Partners": run_partners_eval
    }
    
    if eval_name not in evals:
        raise ValueError(f"Unknown eval '{eval_name}'. Available evals: {list(evals.keys())}")
        
    print(f"\nRunning {eval_name} eval...")
    start_time = time.time()
    
    try:
        success = evals[eval_name]()
        duration = time.time() - start_time
        result = {
            "success": success,
            "duration": f"{duration:.2f}s"
        }
        
        print(f"{eval_name} eval completed in {duration:.2f}s")
        print(f"Status: {'✅ Passed' if success else '❌ Failed'}")
        return result
        
    except Exception as e:
        result = {
            "success": False,
            "error": str(e),
            "duration": f"{time.time() - start_time:.2f}s"
        }
        print(f"❌ {eval_name} eval failed with error: {str(e)}")
        return result

def run_all_evals():
    evals: Dict[str, Callable] = {
        "Google Jobs": run_google_jobs_eval,
        "Wikipedia": run_wikipedia_eval,
        "GitHub Commits": run_github_commits_eval,
        "Home Depot": run_homedepot_eval,
        "Partners": run_partners_eval
    }
    
    results = {}
    total_start_time = time.time()
    
    print("Starting Stagehand Evaluations...")
    print("=" * 50)
    
    for name, eval_func in evals.items():
        print(f"\nRunning {name} eval...")
        start_time = time.time()
        
        try:
            success = eval_func()
            duration = time.time() - start_time
            results[name] = {
                "success": success,
                "duration": f"{duration:.2f}s"
            }
            
            print(f"{name} eval completed in {duration:.2f}s")
            print(f"Status: {'✅ Passed' if success else '❌ Failed'}")
            
        except Exception as e:
            results[name] = {
                "success": False,
                "error": str(e),
                "duration": f"{time.time() - start_time:.2f}s"
            }
            print(f"❌ {name} eval failed with error: {str(e)}")
    
    total_duration = time.time() - total_start_time
    
    print("\n" + "=" * 50)
    print("Evaluation Summary:")
    print(f"Total Duration: {total_duration:.2f}s")
    print(f"Passed: {sum(1 for r in results.values() if r['success'])}/{len(evals)}")
    
    for name, result in results.items():
        status = "✅ Passed" if result["success"] else "❌ Failed"
        print(f"{name}: {status} ({result['duration']})")
        if not result["success"] and "error" in result:
            print(f"  Error: {result['error']}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run Stagehand evaluations')
    parser.add_argument('--eval', type=str, help='Name of specific eval to run (e.g. "Wikipedia", "Google Jobs")')
    parser.add_argument('--list', action='store_true', help='List all available evals')
    args = parser.parse_args()

    if args.list:
        print("Available evals:")
        for eval_name in ["Google Jobs", "Wikipedia", "GitHub Commits", "Home Depot", "Partners"]:
            print(f"- {eval_name}")
    elif args.eval:
        run(args.eval)
    else:
        run_all_evals()
