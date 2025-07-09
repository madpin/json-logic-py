import cProfile
import pstats
from json_logic import jsonLogic

# A moderately complex rule using various operations
sample_rule = {
    "if": [
        {
            "and": [
                {">=": [{"var": "score"}, 75]},
                {"in": [{"var": "category"}, ["A", "B", "C"]]},
                {
                    "some": [
                        {"var": "tags"},
                        {"==": [{"var": ""}, "important"]},
                    ]
                },
            ]
        },
        "Pass",
        "Fail",
    ]
}

sample_data = {
    "score": 80,
    "category": "A",
    "tags": ["review", "important", "final"],
}

# Another rule using map and reduce
complex_rule = {
    "let": {  # Assuming 'let' is not supported, this will be a simple var access for now
              # or we can simulate by directly using the result of a calculation
        "numbers": {"var": "items"}, # items should be a list of numbers
        "doubled_numbers": {
            "map": [
                {"var": "numbers"},
                {"*": [{"var": ""}, 2]}
            ]
        },
        "sum_of_doubled": {
            "reduce": [
                {"var": "doubled_numbers"},
                {"+": [{"var": "current"}, {"var": "accumulator"}]},
                0
            ]
        },
        "result": {"var": "sum_of_doubled"} # We want to get this value
    }
}

# For the complex_rule, we need to structure it such that jsonLogic can resolve it step-by-step
# or test parts of it. JsonLogic doesn't have a native 'let'.
# Let's test the map and reduce parts.

map_reduce_rule = {
    "reduce": [
        {
            "map": [
                {"var": "items"},
                {"*": [{"var": ""}, 2]}
            ]
        },
        {"+": [{"var": "current"}, {"var": "accumulator"}]},
        0
    ]
}

map_reduce_data = {
    "items": list(range(100)) # A list of 100 numbers
}


def run_benchmark():
    for _ in range(1000): # Run multiple times to get more stable profile data
        jsonLogic(sample_rule, sample_data)
        jsonLogic(map_reduce_rule, map_reduce_data)

if __name__ == "__main__":
    profiler = cProfile.Profile()
    profiler.enable()
    run_benchmark()
    profiler.disable()

    stats = pstats.Stats(profiler).sort_stats('cumulative')
    stats.print_stats(20) # Print top 20 cumulative time consumers

    print("\n\nSorted by total time (tottime):")
    stats_tottime = pstats.Stats(profiler).sort_stats('tottime')
    stats_tottime.print_stats(20)
