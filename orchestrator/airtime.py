"""
airtime.py — LoRa on-air time calculation.

Formula reference: Semtech AN1200.13 "LoRa Modem Designer's Guide" §4.
All timing values are in milliseconds.
"""

from __future__ import annotations

import math


def lora_airtime_ms(
    sf: int,
    bw_hz: int,
    cr: int,
    payload_bytes: int,
    preamble_symbols: int = 8,
    crc: bool = True,
    explicit_header: bool = True,
) -> float:
    """Return the on-air time in milliseconds for a LoRa packet.

    Parameters
    ----------
    sf
        Spreading factor (7–12).
    bw_hz
        Bandwidth in Hz (e.g. 125_000, 250_000, 500_000).
    cr
        Coding-rate denominator offset: 1 = CR4/5, 2 = CR4/6,
        3 = CR4/7, 4 = CR4/8.
    payload_bytes
        Number of bytes in the MAC payload.
    preamble_symbols
        Number of preamble symbols (default 8, standard for LoRa).
    crc
        True if a CRC is appended (almost always True in MeshCore).
    explicit_header
        True if the LoRa explicit header is present (MeshCore default).
    """
    # Symbol duration in milliseconds
    t_sym_ms = (2 ** sf) / (bw_hz / 1000.0)

    # Preamble duration
    t_preamble_ms = (preamble_symbols + 4.25) * t_sym_ms

    # Low data-rate optimisation: mandatory when T_sym >= 16 ms
    # (SF11/SF12 at BW=125 kHz; SF12 at BW=250 kHz)
    de = 1 if t_sym_ms >= 16.0 else 0

    h        = 0 if explicit_header else 1
    crc_flag = 1 if crc else 0

    # Number of payload symbols (Semtech formula)
    numerator   = 8 * payload_bytes - 4 * sf + 28 + 16 * crc_flag - 20 * h
    denominator = 4 * (sf - 2 * de)
    payload_symbols = 8 + max(math.ceil(numerator / denominator) * (cr + 4), 0)

    t_payload_ms = payload_symbols * t_sym_ms
    return t_preamble_ms + t_payload_ms
