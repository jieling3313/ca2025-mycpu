// SPDX-License-Identifier: MIT
// Nyancat with Delta-RLE + Huffman decompression

#include <stdint.h>

// Include Huffman compressed data
#include "nyancat-huffman.h"

// VGA MMIO register addresses
#define VGA_BASE 0x30000000u
#define VGA_ID (VGA_BASE + 0x00)
#define VGA_CTRL (VGA_BASE + 0x04)
#define VGA_STATUS (VGA_BASE + 0x08)
#define VGA_UPLOAD_ADDR (VGA_BASE + 0x10)
#define VGA_STREAM_DATA (VGA_BASE + 0x14)
#define VGA_PALETTE(n) (VGA_BASE + 0x20 + ((n) << 2))

// Animation constants
#define FRAME_SIZE 4096
#define FRAME_COUNT 12
#define PIXELS_PER_WORD 8
#define PALETTE_SIZE 14

// Nyancat color palette
static const uint8_t nyancat_palette[14] = {0x01, 0x3F, 0x00, 0x3E, 0x3B,
                                            0x36, 0x30, 0x38, 0x3C, 0x0C,
                                            0x0B, 0x17, 0x2A, 0x3A};

// MMIO functions
static inline void vga_write32(uint32_t addr, uint32_t val)
{
    *(volatile uint32_t *) addr = val;
}

static inline uint32_t vga_read32(uint32_t addr)
{
    return *(volatile uint32_t *) addr;
}

// Pack 8 4-bit pixels
static inline uint32_t pack8_pixels(const uint8_t *pixels)
{
    return (uint32_t) (pixels[0] & 0xF) | ((uint32_t) (pixels[1] & 0xF) << 4) |
           ((uint32_t) (pixels[2] & 0xF) << 8) |
           ((uint32_t) (pixels[3] & 0xF) << 12) |
           ((uint32_t) (pixels[4] & 0xF) << 16) |
           ((uint32_t) (pixels[5] & 0xF) << 20) |
           ((uint32_t) (pixels[6] & 0xF) << 24) |
           ((uint32_t) (pixels[7] & 0xF) << 28);
}

// Initialize palette
void vga_init_palette(void)
{
    for (int i = 0; i < PALETTE_SIZE; i++) {
        vga_write32(VGA_PALETTE(i), nyancat_palette[i] & 0x3F);
    }
    for (int i = PALETTE_SIZE; i < 16; i++) {
        vga_write32(VGA_PALETTE(i), 0x00);
    }
}

// ============================================================================
// Huffman Decompression
// ============================================================================

// Bit stream reader
typedef struct {
    uint32_t buffer;      // Bit buffer
    int bits_available;   // Available bits
    const uint8_t *data;  // Data pointer
    int data_pos;         // Current position
} BitStream;

void bitstream_init(BitStream *bs, const uint8_t *data)
{
    bs->buffer = 0;
    bs->bits_available = 0;
    bs->data = data;
    bs->data_pos = 0;
}

uint32_t bitstream_read_bit(BitStream *bs)
{
    // Refill buffer if empty
    if (bs->bits_available == 0) {
        bs->buffer = bs->data[bs->data_pos++];
        bs->bits_available = 8;
    }

    // Extract MSB
    uint32_t bit = (bs->buffer >> 7) & 1;
    bs->buffer <<= 1;
    bs->bits_available--;

    return bit;
}

uint8_t huffman_decode_opcode(BitStream *bs)
{
    // Tree traversal decoding
    uint16_t current_code = 0;
    int code_len = 0;

    // Match bit by bit
    while (code_len < 16) {  // Max code length
        uint32_t bit = bitstream_read_bit(bs);
        current_code = (current_code << 1) | bit;
        code_len++;

        // Lookup in Huffman table
        for (int i = 0; i < sizeof(huffman_table) / sizeof(HuffmanEntry); i++) {
            if (huffman_table[i].code_len == code_len &&
                huffman_table[i].code == current_code) {
                return huffman_table[i].opcode;
            }
        }
    }

    return 0xFF;  // Error
}

// ============================================================================
// Delta-RLE Decompression
// ============================================================================

static uint8_t frame_buffer[FRAME_SIZE];
static uint8_t prev_frame_buffer[FRAME_SIZE];
static uint8_t opcodes_buffer[8192];  // Decompressed opcodes

// Decompress all opcodes using Huffman
int huffman_decompress_all_opcodes(void)
{
    BitStream bs;
    bitstream_init(&bs, huffman_compressed_data);

    int opcode_count = 0;
    int bits_read = 0;

    while (bits_read < HUFFMAN_BITSTREAM_LEN && opcode_count < 8192) {
        uint8_t opcode = huffman_decode_opcode(&bs);
        opcodes_buffer[opcode_count++] = opcode;

        // Estimate bits read (approximate)
        bits_read += 6;  // Average code length ~6 bits

        if (opcode == 0xFF) {
            // Check if all frames decoded
            if (opcode_count > 4000) {
                break;
            }
        }
    }

    return opcode_count;
}

// Decompress Delta-RLE frame from opcodes
void decompress_frame(int frame_index, const uint8_t *opcodes, int opcode_len)
{
    if (frame_index == 0) {
        // Frame 0: baseline RLE
        int output_index = 0;
        uint8_t current_color = 0;

        for (int i = 0; i < opcode_len && output_index < FRAME_SIZE; i++) {
            uint8_t opcode = opcodes[i];

            if (opcode == 0xFF)
                break;

            if ((opcode & 0xF0) == 0x00) {
                current_color = opcode & 0x0F;
            } else if ((opcode & 0xF0) == 0x20) {
                int count = (opcode & 0x0F) + 1;
                for (int j = 0; j < count && output_index < FRAME_SIZE; j++)
                    frame_buffer[output_index++] = current_color;
            } else if ((opcode & 0xF0) == 0x30) {
                int count = ((opcode & 0x0F) + 1) * 16;
                for (int j = 0; j < count && output_index < FRAME_SIZE; j++)
                    frame_buffer[output_index++] = current_color;
            }
        }

        // Fill remaining
        while (output_index < FRAME_SIZE)
            frame_buffer[output_index++] = 0;

    } else {
        // Frame 1-11: delta
        // Copy previous frame
        for (int i = 0; i < FRAME_SIZE; i++)
            frame_buffer[i] = prev_frame_buffer[i];

        int pos = 0;
        uint8_t current_color = 0;

        for (int i = 0; i < opcode_len && pos < FRAME_SIZE; i++) {
            uint8_t opcode = opcodes[i];

            if (opcode == 0xFF)
                break;

            if ((opcode & 0xF0) == 0x00) {
                current_color = opcode & 0x0F;
            } else if ((opcode & 0xF0) == 0x10) {
                pos += (opcode & 0x0F) + 1;  // Skip
            } else if ((opcode & 0xF0) == 0x20) {
                int count = (opcode & 0x0F) + 1;  // Repeat
                for (int j = 0; j < count && pos < FRAME_SIZE; j++)
                    frame_buffer[pos++] = current_color;
            } else if ((opcode & 0xF0) == 0x30) {
                pos += ((opcode & 0x0F) + 1) * 16;  // Skip long
            } else if ((opcode & 0xF0) == 0x40) {
                int count = ((opcode & 0x0F) + 1) * 16;  // Repeat long
                for (int j = 0; j < count && pos < FRAME_SIZE; j++)
                    frame_buffer[pos++] = current_color;
            } else if ((opcode & 0xF0) == 0x50) {
                pos += ((opcode & 0x0F) + 1) * 64;  // Skip very long
            }
        }
    }

    // Save for next delta
    for (int i = 0; i < FRAME_SIZE; i++)
        prev_frame_buffer[i] = frame_buffer[i];
}

// Upload frame to VGA
void vga_upload_frame(int frame_index)
{
    vga_write32(VGA_UPLOAD_ADDR, ((uint32_t) (frame_index & 0xF) << 16) | 0);

    for (int i = 0; i < FRAME_SIZE; i += PIXELS_PER_WORD) {
        uint32_t packed = pack8_pixels(&frame_buffer[i]);
        vga_write32(VGA_STREAM_DATA, packed);
    }
}

// Simple delay
static inline void delay(uint32_t cycles)
{
    for (uint32_t i = 0; i < cycles; i++)
        __asm__ volatile("nop");
}

int main(void)
{
    // Verify VGA
    uint32_t id = vga_read32(VGA_ID);
    if (id != 0x56474131)
        return 1;

    // Initialize palette
    vga_init_palette();
    vga_write32(VGA_CTRL, 0x01);

    // 1. Huffman decompress all opcodes
    int total_opcodes = huffman_decompress_all_opcodes();

    // 2. Find frame boundaries in opcodes
    int frame_starts[FRAME_COUNT + 1];
    int frame_count = 0;
    frame_starts[0] = 0;

    for (int i = 0; i < total_opcodes && frame_count < FRAME_COUNT; i++) {
        if (opcodes_buffer[i] == 0xFF) {
            frame_starts[++frame_count] = i + 1;
        }
    }

    // 3. Decompress and upload all frames
    for (int frame = 0; frame < FRAME_COUNT; frame++) {
        int start = frame_starts[frame];
        int end = frame_starts[frame + 1];
        int len = end - start;

        decompress_frame(frame, &opcodes_buffer[start], len);
        vga_upload_frame(frame);
        vga_write32(VGA_CTRL, (frame << 4) | 0x01);
    }

    // Step 4: Animate
    for (uint32_t frame = 0;;) {
        vga_write32(VGA_CTRL, (frame << 4) | 0x01);
        delay(50000);
        frame = (frame + 1 < FRAME_COUNT) ? frame + 1 : 0;
    }
}
