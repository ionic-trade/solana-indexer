# Copyright (C) 2025, Ionic.

# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.


"""List of known solana programs"""

KNOWN_PROGRAMS = {
    "pump_fun" : "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",
}

def get_program_by_name(pubkey: str) -> str:
    for name, key in KNOWN_PROGRAMS.items():
        if key == pubkey:
            return name
    return pubkey