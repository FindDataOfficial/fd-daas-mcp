---
name: fd-coding-code-creator
description: >
  Generate Python implementation code from class diagrams and SQLAlchemy schemas.
  Use this skill whenever the user asks to generate code, implement classes,
  create service code, or "write the implementation" from a design. Trigger when
  the user mentions code generation, implementation, service layer, or wants to
  turn diagrams and schemas into working Python code.
---

# Code Creator

Generate Python implementation code for service classes from class diagrams
and SQLAlchemy schemas. The diagram defines what needs to be built, the schema
provides the data layer, and the clear-goal provides business context — this
skill produces the service layer that wires everything together.

## Where things live

- **Input**: `.claude/skills/fd-coding-common-resources/diagram/` — class diagrams (service class definitions) + `.claude/skills/fd-coding-common-resources/schema/` — SQLAlchemy models (data layer)
- **Context**: `.claude/skills/fd-coding-common-resources/goal/clear-goal/` — business constraints and design decisions
- **Output**: `src/` — Python implementation files
- **Directory structure**: Mirror the input (case-insensitive). `.claude/skills/fd-coding-common-resources/diagram/paas/mcp-diagram.yaml` → `src/paas/`

## What gets generated

Only **service classes** — classes from the diagram that are NOT data entities.
Data entities already exist as SQLAlchemy models in `.claude/skills/fd-coding-common-resources/schema/`. Service classes
are the runtime logic: managers, routers, allocators, deployers.

Skip classes whose attributes are all scalars and whose methods are `toDict` /
`fromDict` — those are data entities, handled by fd-coding-schema-creator.

## Before you start

1. **Read `.claude/skills/fd-coding-common-resources/README.md`** — Understand the full FD-Coding pipeline, where shared resources live, and what comes before/after this skill.
2. Read the diagram YAML file to understand all classes and relationships
2. Read the corresponding schema file (mirror path: `.claude/skills/fd-coding-common-resources/diagram/<path>/<name>-diagram.yaml` → `.claude/skills/fd-coding-common-resources/schema/<path>/<name>.py`) to understand the data layer
3. **Read the corresponding clear-goal file** (mirror path, case-insensitive: `.claude/skills/fd-coding-common-resources/diagram/<path>/<name>-diagram.yaml` → `.claude/skills/fd-coding-common-resources/goal/clear-goal/<path>/<name>.md`) for business constraints and design decisions that affect implementation
4. Identify which classes are service classes (skip data entities — they're in `.claude/skills/fd-coding-common-resources/schema/`)
5. Check `src/` for any existing implementation files

## How to classify classes (same heuristic as schema-creator)

- **Data entity** (skip — already in schema): attributes are all scalars (String, int, boolean) or references to other entities. Methods are toDict/fromDict. Don't generate these.
- **Service class** (generate): attributes reference other services, config paths, or runtime state. Methods do orchestration (start, stop, deploy, allocate, reload, route).

## Output structure

Each service class gets its own file. Group related classes into subdirectories
when there are clear subsystem boundaries.

```
src/paas/
├── __init__.py
├── registry.py          # ServerRegistry
├── port_allocator.py    # PortAllocator
├── lifecycle.py         # LifecycleManager
├── nginx_config.py      # NginxConfigManager
├── router.py            # ServerRouter
└── docker_deployer.py   # DockerDeployer
```

Each file should be self-contained but import from `.claude/skills/fd-coding-common-resources/schema/` and other
`src/` modules as needed.

## Code conventions

- **Type hints**: Every method signature uses type hints (Python 3.10+ syntax: `list[X]` not `List[X]`)
- **Docstrings**: Google-style docstrings for public methods
- **Error handling**: Use specific exception types, not bare `except:`
- **Logging**: Use `logging.getLogger(__name__)` for non-trivial services
- **Imports**: Group stdlib → third-party → local (schema/src)
- **Config**: Use constructor injection — config values come in via `__init__`, not hardcoded

## Class implementation guide

### Classes that hold references to other services

When a diagram class has attributes typed as other service classes (e.g.,
`ServerRouter` holds `registry: ServerRegistry`, `lifecycleManager: LifecycleManager`),
use **constructor dependency injection**:

```python
class ServerRouter:
    def __init__(self, registry: ServerRegistry, lifecycle: LifecycleManager, nginx: NginxConfigManager):
        self._registry = registry
        self._lifecycle = lifecycle
        self._nginx = nginx
```

This makes the dependency graph explicit and testable.

### Classes that manage runtime state

For classes like `PortAllocator` or `LifecycleManager` that track runtime
state (allocated ports, running processes), use instance attributes
initialized in `__init__`:

```python
class PortAllocator:
    def __init__(self, start_port: int = 8100, end_port: int = 8199):
        self._start_port = start_port
        self._end_port = end_port
        self._allocated: dict[str, int] = {}  # server_id -> port
```

### Classes that wrap external systems

For `NginxConfigManager` (filesystem) and `DockerDeployer` (Docker CLI),
use subprocess or file I/O with proper error handling. Always check
availability before attempting operations:

```python
class DockerDeployer:
    def __init__(self):
        self._docker_available = self._check_docker()

    def _check_docker(self) -> bool:
        try:
            subprocess.run(["docker", "info"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
```

## Relationships in code

The diagram's relationships section defines how classes interact. Translate
each relationship into code:

- **composition** (A owns B): A creates B in `__init__` or receives it and
  B should not be shared. B has no independent lifecycle.
- **association** (A uses B): B is passed to A's `__init__`. B may be shared
  with other classes.
- **dependency** (A delegates to B): B is used in A's method bodies but not
  stored as an attribute. Import B but don't inject it.
- **inheritance**: Standard Python inheritance.

## Naming conventions

- **File names**: match the source diagram without `-diagram` (e.g., `mcp-diagram.yaml` → `mcp/` directory)
- **Class names**: keep the PascalCase from the diagram (e.g., `ServerRegistry`, `PortAllocator`)
- **Module names**: snake_case of the class name (e.g., `ServerRegistry` → `registry.py`, `NginxConfigManager` → `nginx_config.py`)
- **Method names**: camelCase from the diagram, implemented as snake_case in Python (e.g., `startServer` → `start_server`)

## Workflow

### Phase 1: Analyze

1. Read the diagram, schema, and clear-goal files
2. List all classes and classify each as data entity (skip) or service class (generate)
3. For each service class, identify its dependencies (what other classes it references in attributes)
4. Map relationships to injection patterns (composition → create, association → inject, dependency → import)

### Phase 2: Confirm with the user

Present the plan:

- Which classes will be generated (service classes)
- Which are skipped (data entities, already in schema)
- The file layout under `src/`
- Any design decisions that affect the implementation

### Phase 3: Generate

Write each file to `src/<mirror-path>/`.

**Quality checks before saving:**
- Every method from the diagram is implemented (no stubs unless the method is genuinely out of scope)
- All imports resolve to existing modules (schema/ or other src/ files)
- Constructor injection matches the diagram's attribute types
- Type hints are present on all method signatures
- Error handling covers the obvious failure modes (file not found, process already running, port exhaustion, etc.)

### Phase 4: Validate

1. **Completeness**: Every service class from the diagram has a corresponding file
2. **Import integrity**: `python -c "import ast; ast.parse(open('...').read())"` for each file
3. **Dependency graph**: The import graph matches the diagram's relationship graph — no circular imports
4. **Schema imports**: Service classes that reference data entities import from the correct schema path
