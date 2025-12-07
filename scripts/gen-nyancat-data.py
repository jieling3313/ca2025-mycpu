#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Unified nyancat data generator with configurable compression modes.

Downloads animation data from klange/nyancat repository and applies either:
- Opcode-based RLE compression (baseline, 87% reduction)
- Delta frame encoding (advanced, 91% reduction)

Opcode format (baseline RLE):
  0x0X = SetColor (current color = X, 0-13)
  0x2Y = Repeat Y+1 times (1-16 pixels)
  0x3Y = Repeat (Y+1)*16 times (16-256 pixels)
  0xFF = EndOfFrame

Delta encoding format (--delta mode):
  Frame 0 (baseline):
    0x0X = SetColor (X = color 0-13)
    0x2Y = Repeat (Y+1) times (1-16 pixels)
    0x3Y = Repeat (Y+1)*16 times (16-256 pixels)
    0xFF = EndOfFrame

  Frame 1-11 (delta):
    0x0X = SetColor (X = color 0-13)
    0x1Y = Skip (Y+1) unchanged pixels (1-16)
    0x2Y = Repeat (Y+1) changed pixels (1-16)
    0x3Y = Skip (Y+1)*16 unchanged pixels (16-256)
    0x4Y = Repeat (Y+1)*16 changed pixels (16-256)
    0x5Y = Skip (Y+1)*64 unchanged pixels (64-1024)
    0xFF = EndOfFrame
"""

import argparse
import heapq
import re
import sys
import urllib.request
from collections import Counter
from pathlib import Path
from typing import List, Tuple


def download_animation_data(url: str) -> str:
    """Download animation.c from GitHub repository."""
    try:
        with urllib.request.urlopen(url) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        print(f"Error downloading from {url}: {e}", file=sys.stderr)
        sys.exit(1)


def parse_animation_c(content: str) -> List[List[str]]:
    """
    Parse animation.c to extract frame data.

    Returns list of 12 frames, each frame is list of pixel strings.
    """
    frames = []

    # Find all frame arrays (frame0[] through frame11[])
    for frame_num in range(12):
        pattern = rf'const\s+char\s+\*\s*frame{frame_num}\[\]\s*=\s*\{{([^}}]+)\}}'
        match = re.search(pattern, content, re.DOTALL)

        if not match:
            print(f"Error: Could not find frame{frame_num}[] in animation.c", file=sys.stderr)
            sys.exit(1)

        frame_text = match.group(1)

        # Extract all quoted strings for this frame
        frame_lines = re.findall(r'"([^"]*)"', frame_text)

        # Concatenate all lines into single frame (64 lines × 64 chars = 4096 pixels)
        frame_data = ''.join(frame_lines)

        if len(frame_data) != 4096:
            print(f"Error: frame{frame_num} has {len(frame_data)} pixels, expected 4096", file=sys.stderr)
            sys.exit(1)

        frames.append(list(frame_data))

    return frames


def map_color_to_palette(char: str) -> int:
    """
    Map nyancat color character to palette index.

    Original mapping from klange/nyancat upstream:
    , = dark blue background
    . = white (stars)
    ' = black (border)
    @ = tan (poptart)
    $ = pink (poptart)
    - = red (poptart)
    > = red (rainbow)
    & = orange (rainbow)
    + = yellow (rainbow)
    # = green (rainbow)
    = = light blue (rainbow)
    ; = dark blue (rainbow)
    * = gray (cat face)
    % = pink (cheeks)
    """
    color_map = {
        ',': 0,   # Dark blue background
        '.': 1,   # White (stars)
        "'": 2,   # Black (border)
        '@': 3,   # Tan/Light pink (poptart) -> Light pink/beige
        '$': 5,   # Pink poptart -> Hot pink
        '-': 6,   # Red poptart
        '>': 6,   # Red rainbow (same as red poptart)
        '&': 7,   # Orange rainbow
        '+': 8,   # Yellow rainbow
        '#': 9,   # Green rainbow
        '=': 10,  # Light blue rainbow
        ';': 11,  # Dark blue/Purple rainbow -> Purple
        '*': 12,  # Gray cat face
        '%': 4,   # Pink cheeks
    }
    return color_map.get(char, 0)  # Default to background


def compress_frame_opcode_rle(pixels: List[str]) -> List[int]:
    """
    Compress frame using opcode-based RLE (baseline compression).

    Returns list of opcodes (integers 0-255).
    """
    if len(pixels) != 4096:
        print(f"Error: Frame must have 4096 pixels, got {len(pixels)}", file=sys.stderr)
        sys.exit(1)

    opcodes = []
    i = 0
    current_color = -1

    while i < len(pixels):
        color = map_color_to_palette(pixels[i])

        # Set color if different from current
        if color != current_color:
            opcodes.append(0x00 | color)  # SetColor opcode
            current_color = color

        # Count consecutive pixels of same color
        count = 1
        while i + count < len(pixels) and map_color_to_palette(pixels[i + count]) == color:
            count += 1

        # Encode run length with appropriate opcodes (may need multiple for long runs)
        remaining = count
        while remaining > 0:
            if remaining <= 16:
                # Short repeat: 0x2Y (1-16 pixels)
                opcodes.append(0x20 | (remaining - 1))
                remaining = 0
            elif remaining <= 256:
                # Long repeat: 0x3Y (16-256 pixels in multiples of 16)
                # Emit full chunks of 16
                chunks = min(remaining // 16, 16)  # Max 16 chunks = 256 pixels
                if chunks > 0:
                    opcodes.append(0x30 | (chunks - 1))
                    remaining -= chunks * 16
            else:
                # For very long runs (>256), emit max long repeat (256 pixels)
                opcodes.append(0x30 | 0x0F)  # 16 chunks = 256 pixels
                remaining -= 256

        i += count

    # End of frame marker
    opcodes.append(0xFF)

    return opcodes


def compress_delta_frame(prev_pixels: List[str], curr_pixels: List[str]) -> List[int]:
    """
    Compress delta frame using skip + repeat encoding.

    Returns list of opcodes exploiting temporal coherence.
    """
    if len(prev_pixels) != 4096 or len(curr_pixels) != 4096:
        print("Error: Frames must have 4096 pixels", file=sys.stderr)
        sys.exit(1)

    # Convert to color indices
    prev_colors = [map_color_to_palette(p) for p in prev_pixels]
    curr_colors = [map_color_to_palette(p) for p in curr_pixels]

    opcodes = []
    i = 0
    current_color = -1

    while i < 4096:
        # Count consecutive unchanged pixels
        skip_count = 0
        while i + skip_count < 4096 and prev_colors[i + skip_count] == curr_colors[i + skip_count]:
            skip_count += 1

        # Encode skip if any unchanged pixels
        if skip_count > 0:
            remaining_skip = skip_count
            while remaining_skip > 0:
                if remaining_skip <= 16:
                    # 0x1Y: Skip 1-16 unchanged pixels
                    opcodes.append(0x10 | (remaining_skip - 1))
                    remaining_skip = 0
                elif remaining_skip <= 256:
                    # 0x3Y: Skip 16-256 unchanged pixels (chunks of 16)
                    chunks = min(remaining_skip // 16, 16)
                    if chunks > 0:
                        opcodes.append(0x30 | (chunks - 1))
                        remaining_skip -= chunks * 16
                elif remaining_skip <= 1024:
                    # 0x5Y: Skip 64-1024 unchanged pixels (chunks of 64)
                    chunks = min(remaining_skip // 64, 16)
                    if chunks > 0:
                        opcodes.append(0x50 | (chunks - 1))
                        remaining_skip -= chunks * 64
                else:
                    # Max skip: 1024 pixels
                    opcodes.append(0x50 | 0x0F)
                    remaining_skip -= 1024

            i += skip_count
            if i >= 4096:
                break

        # Handle changed pixels
        color = curr_colors[i]
        if color != current_color:
            opcodes.append(0x00 | color)  # SetColor
            current_color = color

        # Count consecutive changed pixels of same color
        run_len = 1
        while i + run_len < 4096 and \
              curr_colors[i + run_len] == color and \
              prev_colors[i + run_len] != curr_colors[i + run_len]:
            run_len += 1

        # Encode changed run
        remaining_run = run_len
        while remaining_run > 0:
            if remaining_run <= 16:
                # 0x2Y: Repeat 1-16 changed pixels
                opcodes.append(0x20 | (remaining_run - 1))
                remaining_run = 0
            elif remaining_run <= 256:
                # 0x4Y: Repeat 16-256 changed pixels (chunks of 16)
                chunks = min(remaining_run // 16, 16)
                if chunks > 0:
                    opcodes.append(0x40 | (chunks - 1))
                    remaining_run -= chunks * 16
            else:
                # Max run: 256 pixels
                opcodes.append(0x40 | 0x0F)
                remaining_run -= 256

        i += run_len

    opcodes.append(0xFF)
    return opcodes

# ============================================================================
# Huffman Coding Implementation
# ============================================================================

def build_huffman_tree(frequencies: dict) -> List[Tuple[int, str]]:
    """
    Build Huffman tree using min-heap.

    Args:
        frequencies: dict {opcode: count}

    Returns:
        list of (opcode, huffman_code_string)
    """
    # Initialize heap: [weight, [symbol, code]]
    heap = [[weight, [symbol, ""]] for symbol, weight in frequencies.items()]
    heapq.heapify(heap)

    print(f"\n=== Building Huffman Tree ===")
    print(f"Initial nodes: {len(heap)}")

    # Merge nodes until only root remains
    while len(heap) > 1:
        lo = heapq.heappop(heap)
        hi = heapq.heappop(heap)

        # Add '0' prefix to left subtree
        for pair in lo[1:]:
            pair[1] = '0' + pair[1]

        # Add '1' prefix to right subtree
        for pair in hi[1:]:
            pair[1] = '1' + pair[1]

        # Merge and push back
        heapq.heappush(heap, [lo[0] + hi[0]] + lo[1:] + hi[1:])

    # Extract final encoding table
    huffman_codes = sorted(heapq.heappop(heap)[1:], key=lambda p: (len(p[1]), p[0]))

    print(f"Huffman tree built: {len(huffman_codes)} symbols")
    return huffman_codes


def compress_with_huffman(opcodes: List[int], huffman_tree: List[Tuple[int, str]]) -> Tuple[bytes, int]:
    """
    Compress opcodes using Huffman coding.

    Args:
        opcodes: list of opcodes
        huffman_tree: list of (opcode, code_string)

    Returns:
        (compressed_bytes, bitstream_length)
    """
    # Build encoding map
    code_map = {opcode: code for opcode, code in huffman_tree}

    # Convert to bitstream
    bitstream = ''.join(code_map[op] for op in opcodes)

    # Pack into bytes (8 bits per byte)
    compressed = bytearray()
    for i in range(0, len(bitstream), 8):
        byte_bits = bitstream[i:i+8].ljust(8, '0')  # Pad with 0
        compressed.append(int(byte_bits, 2))

    return bytes(compressed), len(bitstream)


def generate_huffman_header(frames: List[List[str]], output_path: Path) -> None:
    """
    Generate header with Delta-RLE + Huffman compression.
    """
    # Step 1: Delta-RLE compression
    print("\n=== Step 1: Delta-RLE Compression ===")
    all_opcodes = []
    compressed_frames = []

    # Frame 0: baseline
    baseline = compress_frame_opcode_rle(frames[0])
    compressed_frames.append(baseline)
    all_opcodes.extend(baseline)
    print(f"Frame  0 (baseline): {len(baseline)} opcodes")

    # Frame 1-11: delta
    for i in range(1, 12):
        delta = compress_delta_frame(frames[i-1], frames[i])
        compressed_frames.append(delta)
        all_opcodes.extend(delta)
        print(f"Frame {i:2d} (delta):    {len(delta)} opcodes")

    total_delta_rle = len(all_opcodes)
    print(f"\nDelta-RLE total: {total_delta_rle} opcodes")

    # Step 2: Build Huffman tree
    print("\n=== Step 2: Huffman Tree Construction ===")
    freq = Counter(all_opcodes)
    huffman_tree = build_huffman_tree(freq)

    # Print encoding table
    print("\nHuffman Encoding Table:")
    print("=" * 60)
    print(f"{'Opcode':<10} {'Freq':<10} {'Code':<20} {'Bits':<10}")
    print("-" * 60)
    for opcode, code in huffman_tree[:10]:  # Show first 10
        print(f"0x{opcode:02x}      {freq[opcode]:<10d} {code:<20s} {len(code):<10d}")
    if len(huffman_tree) > 10:
        print(f"... and {len(huffman_tree) - 10} more")

    # Step 3: Huffman compression
    print("\n=== Step 3: Huffman Compression ===")
    huffman_data, bitstream_len = compress_with_huffman(all_opcodes, huffman_tree)

    total_huffman = len(huffman_data)
    print(f"Huffman compressed: {total_huffman} bytes ({bitstream_len} bits)")

    # Calculate compression ratios
    original_size = 12 * 4096
    delta_rle_ratio = (1 - total_delta_rle / original_size) * 100
    huffman_ratio = (1 - total_huffman / total_delta_rle) * 100
    total_ratio = (1 - total_huffman / original_size) * 100

    print(f"\n=== Compression Summary ===")
    print(f"Original:         {original_size:6d} bytes")
    print(f"After Delta-RLE:  {total_delta_rle:6d} bytes ({delta_rle_ratio:5.1f}% reduction)")
    print(f"After Huffman:    {total_huffman:6d} bytes ({huffman_ratio:5.1f}% additional reduction)")
    print(f"Total reduction:  {total_ratio:5.1f}%")

    # Generate C header file
    with open(output_path, 'w') as f:
        f.write("""
// SPDX-License-Identifier: MIT
// Auto-generated nyancat animation data with Delta-RLE + Huffman compression
// DO NOT EDIT - Generated by scripts/gen-nyancat-data-huffman.py

#ifndef NYANCAT_HUFFMAN_H
#define NYANCAT_HUFFMAN_H

#include <stdint.h>

// Huffman decoding table entry
typedef struct {
    uint8_t opcode;      // Original opcode
    uint8_t code_len;    // Code length in bits
    uint16_t code;       // Huffman code
} HuffmanEntry;

""")

        # Write Huffman table
        f.write(f"// Huffman decoding table ({len(huffman_tree)} entries)\n")
        f.write(f"static const HuffmanEntry huffman_table[{len(huffman_tree)}] = {{\n")
        f.write("    // opcode, len, code\n")

        for opcode, code in huffman_tree:
            code_int = int(code, 2) if code else 0
            f.write(f"    {{0x{opcode:02x}, {len(code):2d}, 0x{code_int:04x}}},")
            f.write(f"  // '{code}' (freq: {freq[opcode]})\n")

        f.write("};\n\n")

        # Write compressed data
        f.write(f"// Huffman compressed data ({len(huffman_data)} bytes, {bitstream_len} bits)\n")
        f.write(f"#define HUFFMAN_BITSTREAM_LEN {bitstream_len}\n\n")

        f.write(f"static const uint8_t huffman_compressed_data[{len(huffman_data)}] = {{\n")
        for i in range(0, len(huffman_data), 16):
            chunk = huffman_data[i:i+16]
            f.write("    " + ", ".join(f"0x{b:02x}" for b in chunk))
            if i + 16 < len(huffman_data):
                f.write(",")
            f.write("\n")
        f.write("};\n\n")

        f.write("#endif // NYANCAT_HUFFMAN_H\n")

    print(f"\nGenerated: {output_path}")
    print(f"Header size: {output_path.stat().st_size} bytes")


def main():
    parser = argparse.ArgumentParser(
        description="Generate nyancat data with Delta-RLE + Huffman compression"
    )
    parser.add_argument(
        '--output', '-o',
        type=Path,
        default=Path('nyancat-huffman.h'),
        help='Output header file path (default: nyancat-huffman.h)'
    )
    parser.add_argument(
        '--url',
        default='https://raw.githubusercontent.com/klange/nyancat/master/src/animation.c',
        help='URL to animation.c'
    )

    args = parser.parse_args()

    # Download and parse animation data
    print(f"Downloading from: {args.url}")
    content = download_animation_data(args.url)

    print("Parsing animation frames...")
    frames = parse_animation_c(content)
    print(f"Parsed {len(frames)} frames, {len(frames[0])} pixels each")

    # Generate Huffman compressed header
    generate_huffman_header(frames, args.output)
    print(f"Output file: {args.output}")

if __name__ == '__main__':
    main()
