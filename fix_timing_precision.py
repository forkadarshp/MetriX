#!/usr/bin/env python3
"""
Script to fix timing precision issues by replacing time.time() with time.perf_counter()
in the TTS/STT benchmarking application.
"""

import re
import os

def fix_timing_in_file(filepath):
    """Replace time.time() with time.perf_counter() in a file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Count replacements
    count = len(re.findall(r'time\.time\(\)', content))
    
    if count > 0:
        # Replace time.time() with time.perf_counter()
        new_content = re.sub(r'time\.time\(\)', 'time.perf_counter()', content)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print(f"Fixed {count} timing calls in {filepath}")
        return count
    else:
        print(f"No timing calls to fix in {filepath}")
        return 0

def main():
    """Main function to fix timing in server.py"""
    server_path = "/app/backend/server.py"
    
    if os.path.exists(server_path):
        total_fixes = fix_timing_in_file(server_path)
        print(f"\nTotal timing precision fixes: {total_fixes}")
    else:
        print(f"File not found: {server_path}")

if __name__ == "__main__":
    main()