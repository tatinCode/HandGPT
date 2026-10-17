#!/usr/bin/env python3
"""Validate the exported reference model's interface and record memory planning."""

import argparse
import json
from pathlib import Path


def validate_methods(methods, model):
    expected_input = [1, 16] if model == "smoke" else [1, 3, 224, 224]
    expected_output = [1, 16] if model == "smoke" else [1, 1000]
    forward = next((method for method in methods if method["name"] == "forward"), None)
    if forward is None:
        raise ValueError("Missing forward method")
    if len(forward["inputs"]) != 1 or len(forward["outputs"]) != 1:
        raise ValueError("Reference model requires exactly one tensor input and output")
    for tensor, shape in ((forward["inputs"][0], expected_input), (forward["outputs"][0], expected_output)):
        if tensor.get("dtype") != "FLOAT" or tensor.get("shape") != shape:
            raise ValueError(f"Unexpected model tensor contract: {tensor}; expected float32 {shape}")
    if forward["inputs"][0].get("dim_order") != list(range(len(expected_input))):
        raise ValueError("Input is not in the expected contiguous logical order")
    if "EthosUBackend" not in forward["delegates"]:
        raise ValueError("The forward method has no Ethos-U delegate; refusing a CPU-only export")
    if any(size < 0 for method in methods for size in method["planned_buffer_bytes"]):
        raise ValueError("Invalid negative planned-buffer size")


def inspect(pte, model):
    from executorch.exir._serialize._program import deserialize_pte_binary
    from executorch.exir.schema import Tensor

    program = deserialize_pte_binary(Path(pte).read_bytes()).program
    methods = []
    for plan in program.execution_plan:
        def describe(index):
            value = plan.values[index].val
            if not isinstance(value, Tensor):
                raise ValueError("Reference input/output is not a tensor")
            return {"shape": value.sizes, "dtype": value.scalar_type.name, "dim_order": value.dim_order}

        methods.append({
            "name": plan.name,
            "inputs": [describe(index) for index in plan.inputs],
            "outputs": [describe(index) for index in plan.outputs],
            "delegates": [delegate.id for delegate in plan.delegates],
            "cpu_operators": [{"name": op.name, "overload": op.overload} for op in plan.operators],
            # Buffer 0 is the constant-memory sentinel, not an arena to allocate.
            "planned_buffer_bytes": plan.non_const_buffer_sizes[1:],
        })
    validate_methods(methods, model)
    return {"schema_version": program.version, "methods": methods, "hardware_verified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pte", type=Path)
    parser.add_argument("--model", choices=("smoke", "mv2"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = inspect(args.pte, args.model)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
