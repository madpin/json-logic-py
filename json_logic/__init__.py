# This is a Python implementation of the following jsonLogic JS library:
# https://github.com/jwadhams/json-logic-js
from __future__ import unicode_literals

import sys
from six.moves import reduce
import logging

logger = logging.getLogger(__name__)

try:
    unicode
except NameError:
    pass
else:
    # Python 2 fallback.
    str = unicode


def if_(*args):
    """Implements the 'if' operator with support for multiple elseif-s."""
    for i in range(0, len(args) - 1, 2):
        if args[i]:
            return args[i + 1]
    if len(args) % 2:
        return args[-1]
    else:
        return None


def soft_equals(a, b):
    """Implements the '==' operator, which does type JS-style coertion."""
    if isinstance(a, str) or isinstance(b, str):
        return str(a) == str(b)
    if isinstance(a, bool) or isinstance(b, bool):
        return bool(a) is bool(b)
    return a == b


def hard_equals(a, b):
    """Implements the '===' operator."""
    if type(a) != type(b):
        return False
    return a == b


def less(a, b, *args):
    """Implements the '<' operator with JS-style type coertion."""
    types = set([type(a), type(b)])
    if float in types or int in types:
        try:
            a, b = float(a), float(b)
        except TypeError:
            # NaN
            return False
    return a < b and (not args or less(b, *args))


def less_or_equal(a, b, *args):
    """Implements the '<=' operator with JS-style type coertion."""
    return (
        less(a, b) or soft_equals(a, b)
    ) and (not args or less_or_equal(b, *args))


def to_numeric(arg):
    """
    Converts a string either to int or to float.
    None is converted to 0 to mimic JavaScript-like behavior in arithmetic.
    This is important, because e.g. {"!==": [{"+": "0"}, 0.0]}
    """
    if arg is None:
        return 0
    if isinstance(arg, str):
        if '.' in arg:
            return float(arg)
        else:
            return int(arg)
    # For bools, True becomes 1, False becomes 0 in JS arithmetic.
    # Python's bools already behave this way in arithmetic contexts (e.g. True + 1 = 2)
    # so no explicit conversion needed for bools if they are to be treated as numbers.
    # However, jsonLogic spec for '+' says "casts to number".
    # For safety, explicitly convert bools if they are not caught by other types.
    if isinstance(arg, bool):
        return int(arg)
    return arg

def plus(*args):
    """Sum converts either to ints or to floats."""
    return sum(to_numeric(arg) for arg in args)


def minus(*args):
    """Also, converts either to ints or to floats."""
    if len(args) == 1:
        return -to_numeric(args[0])
    return to_numeric(args[0]) - to_numeric(args[1])


def merge(*args):
    """Implements the 'merge' operator for merging lists."""
    ret = []
    for arg in args:
        if isinstance(arg, list) or isinstance(arg, tuple):
            ret += list(arg)
        else:
            ret.append(arg)
    return ret


# Sentinel object for missing default values
_MISSING_DEFAULT = object()

def get_var(data, var_name=None, default_val=_MISSING_DEFAULT):
    """Gets variable value from data dictionary."""
    # If var_name is None (e.g. from {"var":[]}), or an empty string, return current data or default.
    if var_name is None or var_name == '':
        if default_val is not _MISSING_DEFAULT and data is None:
            return default_val
        return data

    # Path traversal logic
    current = data
    try:
        # Handle direct integer access for lists
        if isinstance(var_name, int):
            if isinstance(current, list) and -len(current) <= var_name < len(current):
                return current[var_name]
            # If not a list or index out of bounds, fall through to default_val check
            if default_val is not _MISSING_DEFAULT: return default_val
            return None # Default behavior for out-of-bounds without explicit default

        # Dot-notation path for dicts/lists
        # Ensure var_name is a string for split, if it's not an int.
        path_parts = str(var_name).split('.')
        for key_part in path_parts:
            if isinstance(current, dict):
                if key_part not in current:
                    if default_val is not _MISSING_DEFAULT: return default_val
                    return None # Key not found, no default
                current = current[key_part]
            elif isinstance(current, list):
                try:
                    idx = int(key_part)
                    if -len(current) <= idx < len(current):
                        current = current[idx]
                    else: # Index out of bounds
                        if default_val is not _MISSING_DEFAULT: return default_val
                        return None
                except (ValueError, IndexError): # Not a valid int index or other list access error
                    if default_val is not _MISSING_DEFAULT: return default_val
                    return None
            else: # Cannot traverse further (e.g. current is a primitive)
                if default_val is not _MISSING_DEFAULT: return default_val
                return None
        return current
    except (KeyError, TypeError, IndexError, ValueError): # General catch for traversal issues
        if default_val is not _MISSING_DEFAULT: return default_val
        return None # Default behavior if any error during traversal

# Remove the global values_for_var_operator
# values_for_var_operator = []


def missing(data, *args):
    """Implements the missing operator for finding missing variables."""
    not_found = object()
    if args and isinstance(args[0], list):
        args = args[0]
    ret = []
    for arg in args:
        if get_var(data, arg, not_found) is not_found:
            ret.append(arg)
    return ret


def missing_some(data, min_required, args):
    """Implements the missing_some operator for finding missing variables."""
    if min_required < 1:
        return []
    found = 0
    not_found = object()
    ret = []
    for arg in args:
        if get_var(data, arg, not_found) is not_found:
            ret.append(arg)
        else:
            found += 1
            if found >= min_required:
                return []
    return ret


operations = {
    "==": soft_equals,
    "===": hard_equals,
    "!=": lambda a, b: not soft_equals(a, b),
    "!==": lambda a, b: not hard_equals(a, b),
    ">": lambda a, b: less(b, a),
    ">=": lambda a, b: less(b, a) or soft_equals(a, b),
    "<": less,
    "<=": less_or_equal,
    "!": lambda a: not a,
    "!!": bool,
    "%": lambda a, b: a % b,
    "and": lambda *args: reduce(lambda total, arg: total and arg, args, True),
    "or": lambda *args: reduce(lambda total, arg: total or arg, args, False),
    "?:": lambda a, b, c: b if a else c,
    "if": if_,
    "log": lambda a: logger.info(a) or a,
    "in": lambda a, b: a in b if "__contains__" in dir(b) else False,
    "cat": lambda *args: "".join(str(arg) for arg in args),
    "+": plus,
    "*": lambda *args: reduce(lambda total, arg: total * float(arg), args, 1),
    "-": minus,
    "/": lambda a, b=None: a if b is None else float(a) / float(b),
    "min": lambda *args: min(args),
    "max": lambda *args: max(args),
    "merge": merge,
    "count": lambda *args: sum(1 if a else 0 for a in args),
    # New operations to be added here
}

# Forward declaration for jsonLogic to be used in map, filter, etc.
_jsonLogic = None

def _map(data_source, rule):
    """Implements the 'map' operator."""
    if not isinstance(data_source, list):
        return []
    return [_jsonLogic(rule, item) for item in data_source]

def _filter(data_source, rule):
    """Implements the 'filter' operator."""
    if not isinstance(data_source, list):
        return []
    return [item for item in data_source if _jsonLogic(rule, item)]

def _reduce(data_source, rule, initial):
    """Implements the 'reduce' operator."""
    if not isinstance(data_source, list):
        return initial # Or an empty list, an error? tests.json implies initial for null

    # According to tests.json: null data source with initial value returns initial value.
    # {"reduce":[{"var":"integers"},{"+":[{"var":"current"},{"var":"accumulator"}]},0]}, null, 0
    if data_source is None: #This check might be redundant due to isinstance check above
        return initial

    accumulator = initial
    for item in data_source:
        accumulator = _jsonLogic(rule, {'current': item, 'accumulator': accumulator})
    return accumulator

def _all(data_source, rule):
    """Implements the 'all' operator."""
    if not data_source: # Empty array cause "all" to return false.
        return False
    if not isinstance(data_source, list): # Non-list (e.g. null) also false
        return False

    for item in data_source:
        if not _jsonLogic(rule, item):
            return False
    return True

def _none(data_source, rule):
    """Implements the 'none' operator."""
    # Empty array cause "none" to return true.
    if not data_source and isinstance(data_source, list):
        return True
    if not isinstance(data_source, list): # Non-list (e.g. null) also true
        return True

    for item in data_source:
        if _jsonLogic(rule, item):
            return False
    return True

def _some(data_source, rule):
    """Implements the 'some' operator."""
    if not data_source: # Empty array cause "some" to return false.
        return False
    if not isinstance(data_source, list): # Non-list (e.g. null) also false.
        return False

    for item in data_source:
        if _jsonLogic(rule, item):
            return True
    return False

def _substr(source_str, start, length=None):
    """Implements the 'substr' operator."""
    if not isinstance(source_str, str):
        return "" # Or throw error? Jsonlogic.com examples are unclear on non-string input

    s_len = len(source_str)

    # JS-like negative start index
    if start < 0:
        start = s_len + start
        if start < 0: # Still negative after adjustment (e.g., -10 for "abc")
            start = 0

    if length is None:
        return source_str[start:]

    if length == 0:
        return ""

    # JS-like negative length
    if length < 0:
        # "If length is negative, it is treated as number of characters from string end minus length."
        # Effectively, it means "up to length characters from the end".
        # e.g. substr("jsonlogic", -5, -2) == "log" (from index 4 up to index 7 (9-2))
        # e.g. substr("jsonlogic", 1, -5) == "son" (from index 1 up to index 4 (9-5))
        end = s_len + length
        if end < start: # e.g. substr("abc", 0, -4)
             return ""
        return source_str[start:end]

    return source_str[start : start + length]


operations.update({
    "map": lambda ds, rule: _map(ds, rule),
    "filter": lambda ds, rule: _filter(ds, rule),
    "reduce": lambda ds, rule, initial: _reduce(ds, rule, initial),
    "all": lambda ds, rule: _all(ds, rule),
    "none": lambda ds, rule: _none(ds, rule),
    "some": lambda ds, rule: _some(ds, rule),
    "substr": _substr,
})


def jsonLogic(tests, data=None):
    global _jsonLogic # Ensure we are modifying the global
    if _jsonLogic is None:
        _jsonLogic = jsonLogic
    """Executes the json-logic with given data."""

    # If the rule is a list, apply logic to each element and return the new list
    if isinstance(tests, list):
        return [jsonLogic(item, data) for item in tests]

    # You've recursed to a primitive, stop!
    # (If not a list and not a dict, it's a primitive value)
    if not isinstance(tests, dict):
        return tests

    data = {} if data is None else data # Initialize data if it's None, else keep original (even if primitive like 0 or False)

    operator = list(tests.keys())[0]
    values = tests[operator]

    # Easy syntax for unary operators, like {"var": "x"} instead of strict
    # {"var": ["x"]}
    if not isinstance(values, list) and not isinstance(values, tuple):
        values = [values]

    # Recursion!
    # Special handling for argument evaluation for certain operators
    if operator in ['map', 'filter', 'all', 'none', 'some']:
        if not values: # e.g. {"map": []}
            # Handle gracefully, perhaps by returning empty list or based on specific operator needs
            # For now, let map/filter etc. handle empty data_source if values[0] is missing
            if operator == 'map' or operator == 'filter': return []
            if operator == 'all': return False # all of empty set is typically false by convention in jsonLogic tests
            if operator == 'none': return True  # none of empty set is typically true
            if operator == 'some': return False # some of empty set is typically false

        data_source_arg = values[0] if values else None
        rule_arg = values[1] if len(values) > 1 else None # This is the rule literal

        evaluated_data_source = jsonLogic(data_source_arg, data)
        # Rule argument (rule_arg) is passed unevaluated to the operator methods (_map, _filter etc)
        return operations[operator](evaluated_data_source, rule_arg)

    elif operator == 'reduce':
        if len(values) < 3:
            # Invalid reduce call, jsonlogic.com tests don't cover this malformed case explicitly for reduce itself.
            # Defaulting to returning the initial value if provided, else None or error.
            # For now, let operations[operator] call fail if args are insufficient.
            # Or, more safely, return None or raise error.
            # Let's assume tests will only provide valid arg counts for reduce.
            pass

        data_source_arg = values[0]
        rule_arg = values[1] # Rule literal
        initial_val_arg = values[2]

        evaluated_data_source = jsonLogic(data_source_arg, data)
        evaluated_initial_val = jsonLogic(initial_val_arg, data)
        # Rule argument (rule_arg) is passed unevaluated
        return operations[operator](evaluated_data_source, rule_arg, evaluated_initial_val)

    else: # Default behavior: evaluate all arguments
        evaluated_args = [jsonLogic(val, data) for val in values]

        if operator == 'var':
            path = evaluated_args[0] if len(evaluated_args) > 0 else None
            if len(values) > 1: # Default was specified in original rule structure
                # The default value itself should be taken as a literal after its own evaluation.
                default_val_from_rule = evaluated_args[1] if len(evaluated_args) > 1 else None
                return get_var(data, path, default_val_from_rule)
            else: # No default specified in original rule
                return get_var(data, path)

        if operator == 'missing':
            return missing(data, *evaluated_args)
        if operator == 'missing_some':
            return missing_some(data, *evaluated_args)

        if operator not in operations:
            raise ValueError("Unrecognized operation %s" % operator)

        return operations[operator](*evaluated_args)
