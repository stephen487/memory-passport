"""A small JSON Schema (draft 2020-12) checker, standard library only.

It implements the part of the language that PAM's schema and this kit's profile schema use. It is not a general
validator. A keyword it does not know is reported as an error, so a schema edit can never silently stop being
checked. For full coverage use a complete validator (for example the `jsonschema` package); the kit's tests
cross-check this checker against it when it is installed.

Supported: $ref (local "#/..." and the ids in `registry`), type (string or list), enum, const, required,
properties, additionalProperties (bool), items, minItems, uniqueItems, minLength, maxLength, pattern, minimum,
maximum, allOf, if/then/else, format (date-time, uri). Carried but ignored: $schema, $id, $comment, title,
description, default, examples, $defs.
"""
import datetime
import json
import re

_SORTED = {"sort_keys": True}   # one place to say it

_KNOWN = {"$schema", "$id", "$comment", "title", "description", "default", "examples", "$defs", "$ref", "type",
          "enum", "const", "required", "properties", "additionalProperties", "items", "minItems", "uniqueItems",
          "minLength", "maxLength", "pattern", "minimum", "maximum", "allOf", "if", "then", "else", "format"}

_DATETIME = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt][0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?([Zz]|[+-][0-9]{2}:[0-9]{2})$")
_URI = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:\S+$")


def _type_ok(value, name):
    if name == "object":
        return isinstance(value, dict)
    if name == "array":
        return isinstance(value, list)
    if name == "string":
        return isinstance(value, str)
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if name == "boolean":
        return isinstance(value, bool)
    if name == "null":
        return value is None
    return False


def _format_ok(value, fmt):
    if fmt == "date-time":
        if not _DATETIME.match(value):
            return False
        try:
            datetime.datetime.fromisoformat(value.replace("Z", "+00:00").replace("z", "+00:00"))
        except ValueError:
            return False
        return True
    if fmt == "uri":
        return bool(_URI.match(value))
    return True


def _same(a, b):
    return json.dumps(a, **_SORTED) == json.dumps(b, **_SORTED)


class Checker:
    def __init__(self, registry=None):
        # registry: {schema $id: schema dict} for $ref to another document
        self.registry = registry or {}

    def _resolve(self, ref, root):
        if ref.startswith("#"):
            node = root
            for part in [p for p in ref[1:].split("/") if p]:
                node = node[part]
            return node, root
        if ref in self.registry:
            return self.registry[ref], self.registry[ref]
        raise ValueError("unknown $ref (not local, not in the registry): " + ref)

    def errors(self, value, schema, root=None):
        out = []
        self._check(value, schema, root if root is not None else schema, "", out)
        return out

    def _matches(self, value, schema, root):
        probe = []
        self._check(value, schema, root, "", probe)
        return not probe

    def _check(self, value, schema, root, path, errors):
        here = path or "$"
        for key in schema:
            if key not in _KNOWN:
                errors.append(f"{here} - schema keyword not supported by this checker: {key}")
        if "$ref" in schema:
            target, new_root = self._resolve(schema["$ref"], root)
            self._check(value, target, new_root, path, errors)
            return
        if "type" in schema:
            names = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
            if not any(_type_ok(value, n) for n in names):
                errors.append(f"{here} - expected {' or '.join(names)}, got {type(value).__name__}")
                return
        if "const" in schema and (not _same(value, schema["const"])):
            errors.append(f"{here} - must be {json.dumps(schema['const'])}")
        if "enum" in schema and not any(_same(value, e) for e in schema["enum"]):
            errors.append(f"{here} - must be one of {schema['enum']}")
        if isinstance(value, str):
            if "minLength" in schema and len(value) < schema["minLength"]:
                errors.append(f"{here} - too short")
            if "maxLength" in schema and len(value) > schema["maxLength"]:
                errors.append(f"{here} - too long")
            if "pattern" in schema and not re.search(schema["pattern"], value):
                errors.append(f"{here} - does not match the expected format")
            if "format" in schema and not _format_ok(value, schema["format"]):
                errors.append(f"{here} - not a valid {schema['format']}")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in schema and value < schema["minimum"]:
                errors.append(f"{here} - below minimum")
            if "maximum" in schema and value > schema["maximum"]:
                errors.append(f"{here} - above maximum")
        if isinstance(value, dict):
            for name in schema.get("required", []):
                if name not in value:
                    errors.append(f"{here} - missing required field '{name}'")
            props = schema.get("properties", {})
            for name, sub in props.items():
                if name in value:
                    self._check(value[name], sub, root, f"{path}.{name}" if path else name, errors)
            if schema.get("additionalProperties", True) is False:
                for name in value:
                    if name not in props:
                        errors.append(f"{here} - unknown field '{name}' not allowed")
        if isinstance(value, list):
            if "minItems" in schema and len(value) < schema["minItems"]:
                errors.append(f"{here} - too few items")
            if schema.get("uniqueItems") and len({json.dumps(v, **_SORTED) for v in value}) != len(value):
                errors.append(f"{here} - items must be unique")
            if "items" in schema:
                for i, item in enumerate(value):
                    self._check(item, schema["items"], root, f"{path}[{i}]", errors)
        for sub in schema.get("allOf", []):
            self._check(value, sub, root, path, errors)
        if "if" in schema:
            if self._matches(value, schema["if"], root):
                if "then" in schema:
                    self._check(value, schema["then"], root, path, errors)
            elif "else" in schema:
                self._check(value, schema["else"], root, path, errors)
