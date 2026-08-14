import subprocess
import time

def run(cmd):
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(f"ERR: {result.stderr.strip()}")
    return result.stdout.strip()

def main():
    print("--- 1. Triggering 'Quick Draw' (Open and close issue within 5 mins) ---")
    out = run('gh issue create --title "Trigger Quick Draw Achievement" --body "Closing immediately for achievement"')
    
    # Extract issue URL or number from output
    if out:
        lines = out.split('\n')
        url = lines[-1].strip()
        print(f"Created issue: {url}")
        time.sleep(2)
        run(f'gh issue close {url}')
    
    print("\n--- 2. Triggering 'Pull Shark' and 'Pair Extraordinaire' ---")
    run('git checkout -b achievement-branch')
    with open('badge_trigger.txt', 'w') as f:
        f.write('Give me badges')
    run('git add badge_trigger.txt')
    
    # Write commit message to file to avoid quoting issues in shell
    with open('commit_msg.txt', 'w') as f:
        f.write("chore: trigger GitHub achievements\n\nCo-authored-by: github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>")
    
    run('git commit -F commit_msg.txt')
    run('git push -u origin achievement-branch')
    time.sleep(2)
    
    run('gh pr create --title "Trigger Pull Shark" --body "Merging immediately for achievement"')
    time.sleep(2)
    
    run('gh pr merge --merge --delete-branch')
    
    # Clean up
    run('git checkout master')
    run('git pull --rebase')
    
    import os
    if os.path.exists('badge_trigger.txt'): os.remove('badge_trigger.txt')
    if os.path.exists('commit_msg.txt'): os.remove('commit_msg.txt')
    print("\nDone! Check your GitHub profile in a few minutes.")

if __name__ == "__main__":
    main()
