# AGENTS.md — Coding Agent Instructions

You are an expert in Python, Unix shell, and in writing scalable software architectures 
for finance. You write secure, maintainable, and performant code following best practices.
This is a general, non-project specific set of coding guidelines.


## Session start checklist
- Read this file (AGENTS.md)
- Read spec/000-overview.md and spec/010-architecture.md
- Read SESSION.md to continue from where you left off last time.


## Workflow
- We work spec-first. Before implementing, read:
  - $PROJECT_DIR$/spec/000-overview.md and spec/010-architecture.md
  - when available the current feature spec under $PROJECT_DIR$/spec/NNN-*.md (I will name it).
- We use uv, create according pyproject.toml files.
- Create according run configurations for uv-based running, pytest, mypy and linting.


## Version control
- Create a new git branch for each feature or bugfix.
- commit often, with clear commit messages.
- Don't push. I will review your code and merge it into master.


## General
- Follow existing architecture and naming conventions.
- Prefer small, reviewable, incremental changes. Keep diffs minimal.
- Do not introduce new dependencies unless necessary.
- When you need libraries, explain to me and ask me what to use
- Never commit secrets to version control
- Preserve and update project legal notices (LICENSE/NOTICE/README/CONTRIBUTING) when changes affect them.
- The project will be open source, so we can use open source libraries.
- Eventually, the project will be shared on github.
- Primary project language is Python, version >= 3.12 
- Environment is setup via uv, use uv for running code, tests, etc.


## Project file structure
- get project feature descriptions from $PROJECT_DIR$/spec
- put Tests into $PROJECT_DIR$/tests
- put Sources into $PROJECT_DIR$/src
- put input data, work data, output data into $PROJECT_DIR$/data
- put test datasets into $PROJECT_DIR$/testdata
- put documentation into $PROJECT_DIR$/doc
- clone vendor contributions by git into $PROJECT_DIR$/vendor as git submodules, but ask me first


## Language and style
- Write all code identifiers and comments in English.
- use descriptive variable names and comments.
- comment what adds value and not what is obvious from symbol names and code
- Prefer clear, explicit code over cleverness.


## Workflow and IDE
- Locate symbols via IDE navigation / find usages when available.
- Rely on project symbols from IDE where possible, read files only when needed
- Prefer IDE refactorings (Rename/Move) over manual search/replace.


## Python specifics
- Error handling: fail fast with clear exceptions; use assertions; avoid silent fallbacks.
- Use try/except only when you can add meaningful context or recovery; otherwise let exceptions propagate.
- When operations are likely to fail (filesystem, sockets, subprocess), catch and re-raise with
  additional context using `raise ... from exc`.
- Prefer context managers (`with`) for short-lived resources; keep long-lived sockets/files
  as explicit lifecycle-managed objects when appropriate.
- Logging: use existing logging setup; do not add print debugging.
- Follow PEP 8 with 120 character line limit
- Use double quotes for Python strings
- Prefer f-strings for string formatting
- Formatting/linting: adhere to repo config (ruff/black/etc.).
- Use dataclasses for data structures when appropriate.
- Use type annotations for all public symbols or where appropriate.
- Each Python file starts with a module docstring describing its purpose.
- Module docstrings must include:
  - SPDX license identifier and copyright line
  - "AS IS / use at own risk" disclaimer
  - High-level module overview (classes/functions and their relationships)
  - Version metadata block (version, date, author, repository)
- Each public class and public function has a brief docstring.
- Every function and every class (public or private) must have at least a brief docstring.
- Important classes/functions, especially those used across modules, should include more detailed
  docstrings (purpose, inputs/outputs, and any important side effects).
- Add brief comments for non-obvious constants, OS-specific terminology, or portability fallbacks.
- For dataclasses, add brief inline comments for non-obvious fields or describe them in the class docstring.
- Use doctests for small, pure functions where examples add clarity; avoid doctests for I/O,
  timing-dependent behavior, or complex state.


## Testing
- Add/adjust pytest tests for new behavior.
- At least create one test-script for each feature file in $PROJECT_DIR$/spec
- Name test-scripts according to the feature spec file, e.g. spec/010-foo.md -> tests/test_010_foo.py
- In addition to spec-based tests, add unit tests per module or public function for edge cases and error paths.
- Run relevant tests after changes; if tests fail, fix them before reporting success or explain why they cannot be fixed.
- Always run pytest, mypy, and ruff for relevant changes before reporting success.
- Always mock API calls or https: calls in tests
- If a spec implies tests or demo notebooks cannot be added, ask before skipping them.


## Notebooks
- For using functionality interactively we will add demonstration Jupyter notebooks.
- At least create one demo notebook for each feature file in $PROJECT_DIR$/notebooks
- Name notebooks according to the feature spec file, e.g. spec/010-foo.md -> tests/demo_010_foo.ipynb
- The first cell in a notebook should be a text cell containing a title as heading and a short description of the feature 
- In the second cell, notebooks should activate IPython's autoreload extension and import all relevant modules.
- Notebooks should be divided into code cells that group functionality in a useful manner and order, often code cells will build up on previous ones. 
- Notebooks should not mock API calls or https: calls, but use real data.
- If a notebook is impractical or unsafe to add, ask before skipping it.


## Usage
- Add usage documentation to README.md.
- Usage documentation should include information on how to run the code.
- Usage documentation should include a short description of the features


## Output expectations
- If uncertain, propose 2–3 options with tradeoffs.
- Always summarize what changed and why, and list files touched.
