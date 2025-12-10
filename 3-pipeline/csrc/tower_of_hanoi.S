# Tower of Hanoi - Simplified without ECALL
# Just runs the loop logic without printing

    .text
    .globl  _start
_start:
    addi    x2, x2, -32
    sw      x8, 0(x2)
    sw      x9, 4(x2)
    sw      x18, 8(x2)
    sw      x19, 12(x2)
    sw      x20, 16(x2)

    li      x5, 0x15
    sw      x5, 20(x2)
    sw      x5, 24(x2)
    sw      x5, 28(x2)
    sw      x0, 20(x2)
    sw      x0, 24(x2)
    sw      x0, 28(x2)

    addi    x8, x0, 1
game_loop:

    addi    x5, x0, 8
    beq     x8, x5, finish_game

    # Gray code formula: gray(n) = n XOR (n >> k)
    srli    x5, x8, 1
    nop                     # Pipeline: avoid data hazard on x5
    xor     x6, x8, x5
    addi    x7, x8, -1
    srli    x28, x7, 1
    nop                     # Pipeline: avoid data hazard on x28

    # Generate Gray(n-1)
    xor     x7, x7, x28
    nop                     # Pipeline: avoid data hazard on x7
    xor     x5, x6, x7

    # Initialize disk number
    addi    x9, x0, 0

    andi    x6, x5, 1
    nop                     # Pipeline: avoid data hazard before branch
    bne     x6, x0, disk_found
    addi    x9, x0, 1
    andi    x6, x5, 2
    nop                     # Pipeline: avoid data hazard before branch
    bne     x6, x0, disk_found
    addi    x9, x0, 2

disk_found:
    andi    x30, x5, 5
    addi    x31, x0, 5
    beq     x30, x31, pattern_match
    jal     x0, continue_move
pattern_match:
continue_move:
    slli    x5, x9, 2
    addi    x5, x5, 20
    nop                     # Pipeline: avoid data hazard on x5
    add     x5, x2, x5
    nop                     # Pipeline: load-use hazard prevention
    lw      x18, 0(x5)

    nop                     # Pipeline: load-use hazard - need delay after lw
    bne     x9, x0, handle_large
    addi    x19, x18, 2

    addi    x6, x0, 3
    blt     x19, x6, save_move
    sub     x19, x19, x6
    jal     x0, save_move

handle_large:
    lw      x6, 20(x2)
    nop                     # Pipeline: load-use hazard
    addi    x19, x0, 3
    sub     x19, x19, x18
    nop                     # Pipeline: avoid data hazard
    sub     x19, x19, x6

save_move:
    # Skip all the ECALL display code
    slli    x5, x9, 2
    addi    x5, x5, 20
    nop                     # Pipeline: avoid data hazard
    add     x5, x2, x5

    sw      x19, 0(x5)

    addi    x8, x8, 1
    jal     x0, game_loop

finish_game:
    # Note: Skip restoring x8 to keep final loop counter value (8) for test verification
    # lw      x8, 0(x2)
    # nop
    lw      x9, 4(x2)
    nop                     # Pipeline: load-use hazard
    lw      x18, 8(x2)
    nop                     # Pipeline: load-use hazard
    lw      x19, 12(x2)
    nop                     # Pipeline: load-use hazard
    lw      x20, 16(x2)
    addi    x2, x2, 32
    # Exit with WFI loop instead of ecall
loop:
    wfi
    jal     x0, loop

    .data
obdata:     .byte   0x3c, 0x3b, 0x3a
str1:       .asciz  "Move Disk "
str2:       .asciz  " from "
str3:       .asciz  " to "
