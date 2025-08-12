# Copyright (C) 2025, Ionic.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.


"""
Script to transform IDL.json files from incorrect format to correct format.

Transformations:
1. "writable" -> "isMut" (default false if missing)
2. "signer" -> "isSigner" (default false if missing)
3. Remove "pda" field from accounts
4. "type": "pubkey" -> "type": "publicKey"
5. "defined": {"name": "typename"} -> "defined": "typename"
6. Merge type fields from types[] into accounts[] and remove merged types
7. Merge type fields from types[] into events[] and remove merged types
8. Flatten metadata fields to root level and remove metadata object
"""

import json
import sys
import argparse
from pathlib import Path
from typing import Dict, Any, List


def transform_account(account: Dict[str, Any]) -> Dict[str, Any]:
    """Transform a single account object from old format to new format."""
    transformed = account.copy()

    if "writable" in transformed:
        transformed["isMut"] = transformed.pop("writable")
    else:
        transformed["isMut"] = False

    if "signer" in transformed:
        transformed["isSigner"] = transformed.pop("signer")
    else:
        transformed["isSigner"] = False

    if "pda" in transformed:
        del transformed["pda"]

    return transformed


def transform_type_field(obj: Any) -> Any:
    """Recursively transform type fields from 'pubkey' to 'publicKey' and defined types."""
    if isinstance(obj, dict):
        result = {}
        for key, value in obj.items():
            if key == "type" and value == "pubkey":
                result[key] = "publicKey"
            elif key == "defined" and isinstance(value, dict) and "name" in value:
                result[key] = value["name"]
            else:
                result[key] = transform_type_field(value)
        return result
    elif isinstance(obj, list):
        return [transform_type_field(item) for item in obj]
    else:
        return obj


def transform_instruction(instruction: Dict[str, Any]) -> Dict[str, Any]:
    """Transform a single instruction from old format to new format."""
    transformed = instruction.copy()

    if "accounts" in transformed:
        transformed["accounts"] = [
            transform_account(account) for account in transformed["accounts"]
        ]

    transformed = transform_type_field(transformed)

    return transformed


def merge_accounts_with_types(idl_data: Dict[str, Any]) -> Dict[str, Any]:
    """Merge type definitions into accounts and remove merged types."""
    transformed = idl_data.copy()

    if "accounts" not in transformed or "types" not in transformed:
        return transformed

    types_map = {type_def["name"]: type_def for type_def in transformed["types"]}

    merged_types = set()

    for account in transformed["accounts"]:
        account_name = account.get("name")
        if account_name in types_map:
            type_def = types_map[account_name]
            for key, value in type_def.items():
                if key != "name":
                    account[key] = value
            merged_types.add(account_name)

    transformed["types"] = [
        type_def for type_def in transformed["types"]
        if type_def["name"] not in merged_types
    ]

    return transformed


def merge_events_with_types(idl_data: Dict[str, Any]) -> Dict[str, Any]:
    """Merge type definitions into events and remove merged types."""
    transformed = idl_data.copy()

    if "events" not in transformed or "types" not in transformed:
        return transformed

    types_map = {type_def["name"]: type_def for type_def in transformed["types"]}

    merged_types = set()

    for event in transformed["events"]:
        event_name = event.get("name")
        if event_name in types_map:
            type_def = types_map[event_name]

            if ("type" in type_def and
                    isinstance(type_def["type"], dict) and
                    type_def["type"].get("kind") == "struct" and
                    "fields" in type_def["type"]):

                fields = type_def["type"]["fields"]
                for field in fields:
                    field["index"] = False

                event["fields"] = fields

            merged_types.add(event_name)

    transformed["types"] = [
        type_def for type_def in transformed["types"]
        if type_def["name"] not in merged_types
    ]

    return transformed


def flatten_metadata(idl_data: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten metadata fields to root level and remove metadata object."""
    transformed = idl_data.copy()

    if "metadata" not in transformed:
        return transformed

    metadata = transformed["metadata"]

    if isinstance(metadata, dict):
        for key, value in metadata.items():
            transformed[key] = value

    del transformed["metadata"]

    return transformed


def transform_idl(idl_data: Dict[str, Any]) -> Dict[str, Any]:
    """Transform the entire IDL from old format to new format."""
    transformed = idl_data.copy()

    transformed = flatten_metadata(transformed)

    transformed = merge_accounts_with_types(transformed)

    transformed = merge_events_with_types(transformed)

    if "instructions" in transformed:
        transformed["instructions"] = [
            transform_instruction(instruction)
            for instruction in transformed["instructions"]
        ]

    transformed = transform_type_field(transformed)

    return transformed


def main():
    parser = argparse.ArgumentParser(description="Transform IDL.json files to correct format")
    parser.add_argument("input_file", help="Input IDL.json file path")
    parser.add_argument("-o", "--output", help="Output file path (default: overwrite input)")
    parser.add_argument("--backup", action="store_true", help="Create backup of original file")

    args = parser.parse_args()

    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"Error: Input file '{input_path}' does not exist")
        sys.exit(1)

    if args.backup:
        backup_path = input_path.with_suffix(f"{input_path.suffix}.backup")
        backup_path.write_bytes(input_path.read_bytes())
        print(f"Backup created: {backup_path}")

    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            idl_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in '{input_path}': {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading '{input_path}': {e}")
        sys.exit(1)

    transformed_idl = transform_idl(idl_data)

    output_path = Path(args.output) if args.output else input_path

    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(transformed_idl, f, indent=2)
        print(f"Transformed IDL written to: {output_path}")
    except Exception as e:
        print(f"Error writing to '{output_path}': {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
