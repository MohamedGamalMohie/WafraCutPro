"""
Fractional and General Unit Numeric Input Parser
Supports:
- Mixed fractions: '100 1/2', '45 3/8', '12 5/16'
- Simple fractions: '3/4', '1/8'
- Decimal numbers with dot or comma: '100.5', '100,5'
- Standard integers: '1200', '600'
- Strings with units: '1200mm', '48 in', '100 1/2"'
"""
import re
from typing import Union, Tuple, Optional
from fractions import Fraction

def parse_fractional_value(val: Union[str, int, float, None], default: float = 0.0) -> float:
    """
    Parses a string that may represent a fraction, decimal, or integer into a float.
    Returns default (0.0) if parsing fails.
    """
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)

    s = str(val).strip()
    if not s:
        return default

    # Remove quotes, inches symbols, mm, etc.
    s = s.replace('"', '').replace("'", "").replace("mm", "").replace("MM", "").replace("in", "").replace("IN", "").strip()

    # Normalize comma to dot for European style numbers e.g. "100,5"
    # But only if not part of a fraction
    if "/" not in s and "," in s:
        s = s.replace(",", ".")

    # Match mixed fraction: "100 1/2" or "100-1/2"
    mixed_match = re.match(r'^([+-]?\d+)\s*[-_\s]\s*(\d+)\s*/\s*(\d+)$', s)
    if mixed_match:
        whole = int(mixed_match.group(1))
        num = int(mixed_match.group(2))
        denom = int(mixed_match.group(3))
        if denom != 0:
            frac = num / denom
            return float(whole + frac if whole >= 0 else whole - frac)

    # Match simple fraction: "3/4", "1/8"
    frac_match = re.match(r'^([+-]?\d+)\s*/\s*(\d+)$', s)
    if frac_match:
        num = int(frac_match.group(1))
        denom = int(frac_match.group(2))
        if denom != 0:
            return float(num / denom)

    # Match standard decimal or float
    try:
        return float(s)
    except ValueError:
        pass

    # Fallback: extract the first valid number or fraction found
    general_match = re.search(r'(\d+(?:\.\d+)?(?:\s+\d+/\d+)?)', s)
    if general_match:
        matched_str = general_match.group(1)
        if matched_str != s:
            return parse_fractional_value(matched_str, default)

    return default

def format_fractional_display(val: float, tolerance: float = 1e-4) -> str:
    """
    Formats a float cleanly for display.
    If it's an integer, outputs '120'.
    If it's close to a standard fabrication fraction (1/2, 1/4, 1/8, 1/16, 1/32), outputs '100 1/2'.
    Otherwise outputs decimal '100.5'.
    """
    if abs(val - round(val)) < tolerance:
        return str(int(round(val)))

    # Try common fractions with denominators 2, 4, 8, 16, 32
    whole = int(val)
    remainder = abs(val - whole)
    
    for denom in [2, 4, 8, 16, 32]:
        num = round(remainder * denom)
        if abs(remainder - (num / denom)) < tolerance:
            if num == 0:
                return str(whole)
            if num == denom:
                return str(whole + 1 if val >= 0 else whole - 1)
            # Simplify
            f = Fraction(num, denom)
            if whole == 0:
                return f"{f.numerator}/{f.denominator}"
            return f"{whole} {f.numerator}/{f.denominator}"

    return f"{val:.2f}".rstrip('0').rstrip('.')
