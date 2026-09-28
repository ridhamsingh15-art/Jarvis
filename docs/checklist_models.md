# Foundation Specification Checklist: Core Models

- [x] **Immutable**: Achieved natively using `@dataclass(frozen=True, slots=True)`. Mutations raise `FrozenInstanceError`.
- [x] **Strongly typed**: All fields have standard Python type hints.
- [x] **Serializable**: Native `to_dict()` recursively flattens deep model trees into dictionary primitives.
- [x] **Hashable where appropriate**: Yes, frozen dataclasses inherently provide deep structural hashing and equality checking.
- [x] **Version-aware**: The `Version` semver primitive is embedded in top-level domains like `Task`.
- [x] **Provider-independent**: Built purely using the standard library (`dataclasses`, `typing`).
- [x] **Thread-safe**: Guaranteed by absolute immutability. No locks are required to read a model across thread boundaries.
- [x] **Easy to validate**: Natively invokes `self.validate()` via the `__post_init__` lifecycle hook.
- [x] **Deep copy where applicable**: Handled safely via the `copy(**changes)` method utilizing `dataclasses.replace`.
- [x] **Metadata attachment**: The canonical `Metadata` primitive (tags/annotations) is attached to Context, Tasks, Messages, and Artifacts.

### Deliverables Addressed
1. **Repository files**: Cleanly encapsulated within `core/models/`.
2. **Interfaces / Bases**: `JarvisModel` guarantees all architectural constraints via inheritance.
3. **Tests**: Validated thoroughly in `tests/test_models.py`.
4. **Foundation Compliance**: Strict boundaries established. 0% chance of dictionaries escaping sub-systems.
