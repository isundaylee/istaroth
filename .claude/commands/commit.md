Stage and commit changes made in the current working directory.

**Guidelines:**
- Write concise commit messages that explain WHY, not just WHAT
- Use bullet points only when multiple distinct changes are included
- Follow the project's commit message style (check recent commits with `git log`)
- Include small auxiliary changes (e.g., CLAUDE.md updates) in the same commit
- Run pre-commit hooks first to ensure code quality

**Process:**
1. Run `git status` and `git diff` to review changes
2. Run pre-commit checks (`uv run pre-commit run --all-files`)
3. Stage all relevant changes with `git add`
4. Create commit with descriptive message ending with Claude attribution
