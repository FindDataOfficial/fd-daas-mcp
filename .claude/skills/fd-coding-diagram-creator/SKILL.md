---
name: fd-coding-diagram-creator
description: >
  Create class diagrams in YAML format before implementing features.
  Use this skill whenever the user asks to create a diagram, design a class
  structure, model classes, map out architecture, or wants to visualize
  relationships between components. Also use it when the user mentions
  "class diagram", "UML", "entity relationship", "data model", "code
  structure", "design the classes", or "before implementing". Trigger
  especially when the user is about to build something and hasn't yet
  designed the class layout — this skill helps them think through the
  design before writing code.
---

# Diagram Creator

Create class diagrams in YAML format following this project's conventions.
The diagram serves as a design artifact — it captures the class structure,
attributes, methods, and relationships before any code is written, so the
implementation has a clear blueprint.

## Where things live

- **Template**: `.claude/skills/fd-coding-common-resources/template/diagram/template.diagram.yaml` — the canonical schema with placeholder data
- **Input**: `.claude/skills/fd-coding-common-resources/goal/clear-goal/` — refined goals with design decisions (the primary input for forward-design)
- **Context**: `.claude/skills/fd-coding-common-resources/goal/initial-goal/` — original goals with full requirements (may contain details lost in refinement)
- **Output**: `.claude/skills/fd-coding-common-resources/diagram/` — generated diagrams go here
- **Existing diagrams**: `.claude/skills/fd-coding-common-resources/diagram/` — check for prior work before creating a new one
- **Directory structure**: Mirror the source's directory structure. `.claude/skills/fd-coding-common-resources/goal/clear-goal/PAAS/mcp.md` → `.claude/skills/fd-coding-common-resources/diagram/paas/mcp-diagram.yaml`. Keep the same relative path (case-insensitive) so diagrams are easy to find from their source.

## Before you start

1. **Read `.claude/skills/fd-coding-common-resources/README.md`** — Understand the full FD-Coding pipeline, where shared resources live, and what comes before/after this skill.
2. Read `.claude/skills/fd-coding-common-resources/template/diagram/template.diagram.yaml` to understand the exact YAML schema
2. **Read the corresponding clear-goal file** — The clear-goal contains refined steps, design decisions, and constraints that shape the class design. Mirror the path: `.claude/skills/fd-coding-common-resources/goal/clear-goal/<path>/<name>.md` → `.claude/skills/fd-coding-common-resources/diagram/<path>/<name>-diagram.yaml`. If the user explicitly passes a different source file, use that instead.
3. **Read the original initial-goal file** — The clear-goal is a summary of changes. The initial-goal has the full requirements, steps, and success criteria. Derive the path from the clear-goal's `source` field, or mirror from the clear-goal path: `.claude/skills/fd-coding-common-resources/goal/clear-goal/<path>/<name>.md` → `.claude/skills/fd-coding-common-resources/goal/initial-goal/<path>/<name>.md`.
4. Check `.claude/skills/fd-coding-common-resources/diagram/` for any existing diagrams that relate to the current task
5. If the user mentions a specific codebase or feature, read the relevant source files to understand the domain

## YAML schema

The template defines two top-level sections:

### classes

Each class entry has:
```yaml
- name: ClassName           # PascalCase, descriptive
  attributes:               # data members
    - visibility: "-"       # - private, + public, # protected
      name: fieldName       # camelCase
      type: String          # String, int, boolean, List<X>, custom types
  methods:                  # behavior
    - visibility: "+"
      name: methodName      # camelCase
      return_type: void     # void, String, int, boolean, List<X>, custom types
      parameters:           # can be empty list []
        - name: paramName
          type: String
```

### relationships

Each relationship has:
```yaml
- type: inheritance | association | composition | dependency
  from: SourceClass         # must match a class name from above
  to: TargetClass           # must match a class name from above
  label: "describes"        # optional, human-readable
  multiplicity:             # optional, only for association/composition
    from: "1"               # "1", "0..1", "1..*", "many", etc.
    to: "1..*"
```

**Relationship semantics:**
- **inheritance**: "is-a" — Child inherits from Parent. Only use when subclassing is real.
- **composition**: "has-a" (strong) — Container owns parts; parts don't exist independently.
- **association**: "uses-a" (weak) — Objects interact but have independent lifecycles.
- **dependency**: "depends-on" — A method uses B as a parameter or return type without holding a reference.

## Workflow

### Phase 1: Understand

1. **Read the code** (if reverse-engineering): Scan the relevant source files. Look for class definitions, field declarations, method signatures, imports, and constructor patterns. Pay attention to what classes reference each other.

2. **Read the feature description** (if forward-designing): Extract nouns as candidate classes and verbs as candidate methods. Think about responsibilities — each class should have a single, clear purpose.

3. **Check existing diagrams**: Look in `.claude/skills/fd-coding-common-resources/diagram/` for any diagrams that overlap with or relate to the current task. You may need to extend an existing diagram rather than start fresh.

### Phase 2: Plan

Enter plan mode. Design the class diagram by thinking through:

- **What classes exist?** List every entity that needs representation. For each, identify its core responsibility.
- **What data does each class hold?** Attributes should be necessary and sufficient — not speculative.
- **What does each class do?** Methods should represent real behavior, not boilerplate (skip obvious getters/setters unless they're the point of the class).
- **How do classes relate?** Draw relationships carefully. Prefer association over composition unless the lifecycle is truly tied. Only use inheritance when there's a genuine "is-a" relationship — composition is often a better choice.
- **What's the visibility?** Public (+) for the API surface, private (-) for internal state, protected (#) for things subclasses need.

Present the plan to the user. Ask clarifying questions when:
- The feature description is ambiguous about class boundaries
- It's unclear whether a relationship is composition or association
- A class seems to have too many responsibilities (god class smell)
- There's an obvious design choice the user might want to weigh in on (e.g., inheritance vs composition)

### Phase 3: Generate

Once the user approves the plan, generate the YAML file.

**Naming conventions:**
- Class names: PascalCase (e.g., `UserService`, `OrderRepository`)
- Attribute/method names: camelCase (e.g., `userId`, `calculateTotal`)
- File name: kebab-case, descriptive (e.g., `mcp-diagram.yaml`, `order-system.yaml`)
- Directory: mirror the source's directory structure (e.g., `.claude/skills/fd-coding-common-resources/goal/initial-goal/PAAS/mcp.md` → `.claude/skills/fd-coding-common-resources/diagram/paas/mcp-diagram.yaml`)

**Quality checks before saving:**
- Every relationship `from` and `to` references a class that exists in the `classes` list
- No duplicate class names
- Attribute types are specific (not `Object` or `Any`)
- Method parameters have both `name` and `type`
- Visibility is specified on every attribute and method

### Phase 4: Validate

Before considering the diagram complete, validate it:

1. **Schema conformance**: Every required field is present. Classes have `name`, `attributes`, and `methods`. Relationships have `type`, `from`, and `to`.
2. **Referential integrity**: Every `from` and `to` in relationships matches a class `name`.
3. **Type consistency**: Attribute and parameter types reference either primitives (`String`, `int`, `boolean`, `void`) or other class names from the diagram. If a type references a class, that class should exist in the diagram.
4. **Semantic sanity**: No class with zero attributes and zero methods (unless it's a marker interface). No orphan classes (classes with no relationships when others have them — sometimes valid, but flag it).

If validation fails, fix the issues and re-validate. Do not save a diagram that fails validation.

### Phase 5: Offer to continue the pipeline

After saving the diagram, **ask the user**: "Diagram saved. Want to generate the SQLAlchemy schema from it? I can run `/fd-coding-schema-creator` with this diagram."

If the user says yes, invoke the Skill tool with `skill: "fd-coding-schema-creator"` and pass the diagram file path as args. This chains the pipeline: diagram → schema → code.

If the user says no or "later", that's fine — they can always run fd-coding-schema-creator separately.

## Example

Given this Python code:
```python
class Order:
    def __init__(self, order_id: str, customer: Customer):
        self._order_id = order_id
        self._customer = customer
        self._items: list[OrderItem] = []
        self._status = "pending"

    def add_item(self, item: OrderItem) -> None: ...
    def calculate_total(self) -> float: ...
    def submit(self) -> None: ...

class OrderItem:
    def __init__(self, product: Product, quantity: int): ...
    def subtotal(self) -> float: ...

class Customer:
    def __init__(self, name: str, email: str): ...
```

The resulting diagram would follow the format in `scripts/template.yaml`.

Notice: `Product` is referenced as a type but doesn't have its own class entry — it's an external dependency. This is fine, but the diagram should note it (or include it if the scope warrants).

## Edge cases

- **Large codebases**: Don't try to diagram everything. Focus on the subsystem the user asked about. If they say "the whole project", ask them to narrow the scope — a diagram with 50 classes is unreadable.
- **Multiple diagrams**: If the user asks for diagrams of several subsystems, create separate files in `.claude/skills/fd-coding-common-resources/diagram/` (e.g., `diagram/auth.yaml`, `diagram/payments.yaml`).
- **Updating an existing diagram**: If `diagram/<name>.yaml` already exists, don't overwrite it silently. Show what changed and ask for confirmation.
- **Empty methods list**: A class with no methods is valid (e.g., a DTO or value object). Use `methods: []`.
- **External types**: If a class references a type from a library or another module, include it in the type field but don't create a class entry unless it's in scope.
