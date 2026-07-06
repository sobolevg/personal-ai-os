# GitHub Publish

Target owner: `sobolevg`  
Target repository: `personal-ai-os`  
Visibility: private

## Preferred Command

When GitHub CLI is available and authenticated:

```bash
cd personal-ai-os
gh repo create sobolevg/personal-ai-os --private --source=. --remote=origin --push
```

## Manual Alternative

1. Create a private repository named `personal-ai-os` under `sobolevg`.
2. Add it as `origin`.
3. Push `main` and tags.

```bash
cd personal-ai-os
git remote add origin git@github.com:sobolevg/personal-ai-os.git
git push -u origin main
git push origin --tags
```

## Current Environment Note

The local Codex environment used for the baseline did not have `gh` installed,
so the repository was prepared locally first.
