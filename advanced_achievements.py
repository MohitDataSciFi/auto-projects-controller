import subprocess
import time
import json
import os

def run(cmd, shell=False):
    print(f"Running: {cmd}")
    if shell:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    else:
        result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.strip()

def run_gql(query, variables):
    cmd = ["gh", "api", "graphql", "-f", f"query={query}"]
    for k, v in variables.items():
        cmd.extend(["-F", f"{k}={v}"])
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stderr:
        print("GQL ERR:", result.stderr)
    return json.loads(result.stdout)

def trigger_pull_shark():
    print("\n===============================================")
    print("TRIGGERING PULL SHARK (Bronze Tier)")
    print("===============================================")
    # 15 PRs
    for i in range(1, 16):
        print(f"\n>>> PR {i}/15")
        branch = f"pull-shark-{i}"
        run(["git", "checkout", "-b", branch])
        
        with open("badge_trigger.txt", "a") as f:
            f.write(f"\nShark {i}")
            
        run(["git", "add", "badge_trigger.txt"])
        run(["git", "commit", "-m", f"chore: pull shark tier {i}"])
        run(["git", "push", "-u", "origin", branch])
        
        time.sleep(2)
        run(["gh", "pr", "create", "--title", f"Pull Shark PR {i}", "--body", "Automated PR"])
        
        time.sleep(2)
        run(["gh", "pr", "merge", "--merge", "--delete-branch"])
        
        run(["git", "checkout", "master"])
        run(["git", "pull", "--rebase"])

def trigger_galaxy_brain():
    print("\n===============================================")
    print("TRIGGERING GALAXY BRAIN")
    print("===============================================")
    
    # 1. Enable discussions
    run(["gh", "api", "-X", "PATCH", "repos/MohitDataSciFi/auto-projects-controller", "-f", "has_discussions=true"])
    time.sleep(2)
    
    # 2. Get Repo ID and Q&A Category ID
    query_repo = """
    query($owner: String!, $name: String!) {
      repository(owner: $owner, name: $name) {
        id
        discussionCategories(first: 10) {
          nodes {
            id
            name
          }
        }
      }
    }
    """
    data = run_gql(query_repo, {"owner": "MohitDataSciFi", "name": "auto-projects-controller"})
    repo_id = data['data']['repository']['id']
    categories = data['data']['repository']['discussionCategories']['nodes']
    
    # Prefer Q&A category, otherwise pick the first one
    qa_category_id = next((c['id'] for c in categories if c['name'] == 'Q&A'), categories[0]['id'])
    
    # 3. Create 2 Discussions and Mark as Answered
    for i in range(1, 3):
        create_disc = """
        mutation($repoId: ID!, $categoryId: ID!, $title: String!, $body: String!) {
          createDiscussion(input: {repositoryId: $repoId, categoryId: $categoryId, title: $title, body: $body}) {
            discussion {
              id
            }
          }
        }
        """
        data = run_gql(create_disc, {
            "repoId": repo_id,
            "categoryId": qa_category_id,
            "title": f"Galaxy Brain Automated Test {i}",
            "body": "This is a question to trigger the achievement."
        })
        disc_id = data['data']['createDiscussion']['discussion']['id']
        
        add_comment = """
        mutation($discId: ID!, $body: String!) {
          addDiscussionComment(input: {discussionId: $discId, body: $body}) {
            comment {
              id
            }
          }
        }
        """
        data = run_gql(add_comment, {
            "discId": disc_id,
            "body": "This is the answer!"
        })
        comment_id = data['data']['addDiscussionComment']['comment']['id']
        
        mark_ans = """
        mutation($commentId: ID!) {
          markDiscussionCommentAsAnswer(input: {id: $commentId}) {
            clientMutationId
          }
        }
        """
        run_gql(mark_ans, {"commentId": comment_id})
        print(f"Created discussion {i}, answered, and marked as accepted answer!")

def main():
    trigger_galaxy_brain()
    trigger_pull_shark()
    
    print("\nCleaning up...")
    if os.path.exists('badge_trigger.txt'):
        os.remove('badge_trigger.txt')
        run(["git", "add", "badge_trigger.txt"])
        run(["git", "commit", "-m", "chore: cleanup achievement triggers"])
        run(["git", "push"])
        
    print("\n🎉 DONE! You should receive Galaxy Brain and Bronze Pull Shark shortly!")

if __name__ == "__main__":
    main()
