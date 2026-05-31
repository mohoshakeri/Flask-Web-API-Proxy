# Python Code Style Guide

---

## Directory Layout

```
services/       — Third-party integrations (Redis, SMS, Celery)
tools/          — Pure Python utilities with no Django dependency
utils/          — Utilities (base classes, permissions, validators, middlewares, logging)
core/           — Project files (Like src directory)
manager/        — Internal admin management app
CONSTANTS.py    — All magic numbers, strings, time values, cache key prefixes
```

---

## Comments

Write comments in English. Format: `# Capital Words Case`.

```python
# --- Database Section ---

# Compute Final Price After Tax
total: float = price * (1 + tax_rate)
```

No docstrings except where necessary to describe a public API.
When used, keep docstrings minimal — one line for simple functions, short summary for classes.

---

## Type Annotations

All variables, attributes, function parameters, and return types must be explicitly annotated.

```python
user_id: int = 42
name: str = "Ali"
tags: list[str] = ["admin", "staff"]

def get_user(user_id: int) -> dict[str, str] | None:
    ...

def process(items: list[int], multiplier: float = 1.0) -> list[float]:
    ...
```

Use `|` union syntax (Python 3.10+) over `Optional[X]`.

---

## String Formatting — `.format()` over f-strings

```python
# Wrong
message = f"Hello {name}, your order #{order_id} is ready"

# Correct
message = "Hello {}, your order #{} is ready".format(name, order_id)
```

---

## Naming Conventions

| Entity              | Convention        | Example                  |
|---------------------|-------------------|--------------------------|
| Variables           | `snake_case`      | `user_count`             |
| Functions           | `snake_case`      | `get_active_users`       |
| Classes             | `PascalCase`      | `PaymentProcessor`       |
| Constants           | `UPPER_SNAKE`     | `MAX_RETRY_COUNT`        |
| Private attributes  | `_leading_underscore` | `_cache`             |
| Dunder methods      | `__dunder__`      | `__init__`, `__str__`    |

---

## Early Return Pattern

Avoid nested `if/else`. Use guard clauses at the top.

```python
# Wrong
def process_order(order: Order) -> str:
    if order:
        if order.is_paid:
            if not order.is_shipped:
                return ship(order)
            else:
                return "Already shipped"
        else:
            return "Not paid"
    else:
        return "Order not found"

# Correct
def process_order(order: Order | None) -> str:
    if not order:
        return "Order not found"
    if not order.is_paid:
        return "Not paid"
    if order.is_shipped:
        return "Already shipped"
    return ship(order)
```

---

## Constants — No Magic Numbers or Strings

All magic values go in a dedicated constants file or module.

```python
# Wrong
if retry_count > 3:
    sleep(60)

# Correct
# In constants.py
MAX_RETRY_COUNT: int = 3
RETRY_COOLDOWN_SECONDS: int = 60

# In usage
if retry_count > MAX_RETRY_COUNT:
    sleep(RETRY_COOLDOWN_SECONDS)
```

---

## Functions — Single Responsibility

Each function does one thing. If a function needs a comment like `# Then Do This`, split it.

```python
# Wrong — mixed concerns
def register_user(data: dict) -> User:
    user = User(**data)
    user.save()
    send_welcome_email(user.email)
    log_event("user_registered", user.id)
    return user

# Correct — separate concerns, compose at call site
def create_user(data: dict) -> User:
    user = User(**data)
    user.save()
    return user

def on_user_registered(user: User) -> None:
    send_welcome_email(user.email)
    log_event("user_registered", user.id)
```

---

## Classes

Prefer dataclasses for data containers. Use `__slots__` when instantiated heavily.

```python
from dataclasses import dataclass, field


@dataclass
class Config:
    host: str
    port: int = 8080
    tags: list[str] = field(default_factory=list)
```

Use `@property` for derived values. Check for annotation before computing:

```python
@property
def full_name(self) -> str:
    if hasattr(self, "_full_name"):
        return self._full_name
    return "{} {}".format(self.first_name, self.last_name)
```

---

## Imports

Order: stdlib → third-party → local. Separate groups with one blank line.

```python
import os
import sys
from pathlib import Path

import requests
from pydantic import BaseModel

from tools.datetime import now
from tools.jwt import decode_token
```

Never use wildcard imports (`from module import *`) except in `__init__.py` with `__all__` defined.

```python
# In package/__init__.py
from .utils import helper_one, helper_two

__all__: list[str] = ["helper_one", "helper_two"]
```

---

## Error Handling

Be explicit. Never silence exceptions without logging.

```python
# Wrong
try:
    result = risky_operation()
except Exception:
    pass

# Wrong — too broad without context
try:
    result = risky_operation()
except Exception as e:
    print(e)

# Correct
try:
    result = risky_operation()
except ValueError as e:
    logger.warning(msg={"message": "Invalid value", "error": str(e)})
    raise
except ConnectionError as e:
    logger.error(msg={"message": "Connection failed", "error": str(e)})
    return None
```

---

## Mutable Default Arguments

Never use mutable objects as default arguments.

```python
# Wrong — shared across all calls
def append_item(item: str, items: list[str] = []) -> list[str]:
    items.append(item)
    return items

# Correct
def append_item(item: str, items: list[str] | None = None) -> list[str]:
    if items is None:
        items = []
    items.append(item)
    return items
```

---

## Truthiness

Use Python's natural truthiness checks.

```python
# Wrong
if len(items) > 0:
    ...
if name != None:
    ...
if is_active == True:
    ...

# Correct
if items:
    ...
if name is not None:
    ...
if is_active:
    ...
```

---

## Comprehensions

Use comprehensions for simple transformations. Use loops for anything with side effects or multi-step logic.

```python
# Correct — simple transformation
active_ids: list[int] = [u.id for u in users if u.is_active]

# Wrong — side effects in comprehension
emails: list[str] = [send_email(u) for u in users]  # Never do this

# Correct — side effects in loop
for user in users:
    send_email(user)
```

---

## Logging

Use structured log messages. Always include context.

```python
import logging

logger = logging.getLogger("module.submodule")

logger.info({"message": "User logged in", "user_id": user_id})
logger.warning({"message": "Retry attempt", "attempt": attempt, "max": MAX_RETRY_COUNT})
logger.error({"message": "Payment failed", "order_id": order_id, "reason": str(e)})
```

---

## File Organization

| Location      | Purpose                                              |
|---------------|------------------------------------------------------|
| `tools/`      | Pure Python utilities, no framework dependency       |
| `utils/`      | Framework-dependent utilities                        |
| `CONSTANTS.py`| All magic values, cache prefixes, config defaults    |
| `services/`   | Third-party integrations (Redis, SMS, queues)        |

---

## Security — Zero-Trust Access

Default is deny. Access must be explicitly granted.
