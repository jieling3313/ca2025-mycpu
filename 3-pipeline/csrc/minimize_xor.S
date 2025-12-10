# Assignment2_Problem2429_MinimizeXOR_branchlessclz.S

# Input: a0: num1, a1: num2

.global minimizeXor
.globl _start

.text

_start:
    # For testing: set up test inputs
    li      a0, 3       # Example: num1 = 3
    li      a1, 5       # Example: num2 = 5
    jal     ra, minimizeXor
    # Result in a0
    sw      a0, 0(zero) # Store result at memory address 0

loop_end:
    j       loop_end

.globl minimizeXor
minimizeXor:
    # Stack: ra, s0, s1, s2, s3, s4
    addi    sp, sp, -24
    sw      ra, 20(sp)
    sw      s0, 16(sp) # s0: num1
    sw      s1, 12(sp) # s1: bit_budget (k) from num2
    sw      s2, 8(sp)  # s2: result x
    sw      s3, 4(sp)  # s3: loop counter (i)
    sw      s4, 0(sp)  # s4: temp bit check

    mv      s0, a0 # num1(s0)

    # k = popcount(num2)
    mv      a0, a1 # num2(a1) -> a0/popcount
    jal     ra, popcount
    mv      s1, a0 # s1 = k
    nop             # Pipeline: avoid data hazard

    li      s2, 0  # result x = 0

    # Greedy search num1 high bits -> greedy_high_loop
    mv      a0, s0 # num1(s0) -> a0/branchless_clz
    beqz    a0, skip_high_loop # if (num1 == 0){ skip }
    jal     ra, branchless_clz

    li      t0, 31
    nop             # Pipeline: avoid data hazard
    sub     s3, t0, a0 # s3 = i = msb_position of num1
    jal     x0, greedy_high_loop
skip_high_loop:
    # if num1 == 0
    jal     x0, fill_low_bits_check

greedy_high_loop:
    bltz    s3, fill_low_bits_check # while (i >= 0 && k > 0)
    beqz    s1, fill_low_bits_check

    # t1 = (num1 >> i) & 1
    srl     t1, s0, s3
    nop             # Pipeline: avoid data hazard
    andi    t1, t1, 1
    nop             # Pipeline: avoid data hazard before branch

    beqz    t1, greedy_high_continue # if (t1 == 0){ skip }

    # num1 (t1 == 1){ x |= (1 << i) }
    li      t2, 1
    sll     t2, t2, s3
    nop             # Pipeline: avoid data hazard
    or      s2, s2, t2 # x |= (1 << i)

    addi    s1, s1, -1 # k--

greedy_high_continue:
    addi    s3, s3, -1 # i--
    jal     x0, greedy_high_loop

fill_low_bits_check:
    beqz    s1, done # if (k == 0){ done }

    # low_bit -> 1
    li      s3, 0 # i = 0

fill_low_loop:
    beqz    s1, done # while (k > 0)

    srl     t1, s2, s3  # t1 = (x >> i) & 1
    nop             # Pipeline: avoid data hazard
    andi    t1, t1, 1
    nop             # Pipeline: avoid data hazard before branch

    bnez    t1, fill_low_continue # if(bit == 1){ skip }

    # if bit(i/s3) == 0
    li      t2, 1
    sll     t2, t2, s3
    nop             # Pipeline: avoid data hazard
    or      s2, s2, t2    # x |= (1 << i)

    addi    s1, s1, -1    # k--

fill_low_continue:
    addi    s3, s3, 1     # i++
    li      t0, 32
    bge     s3, t0, done   # if(i == 32){ done }
    jal     x0, fill_low_loop

done:
    mv      a0, s2 # result(a0)
    lw      s4, 0(sp)
    nop             # Pipeline: load-use hazard
    lw      s3, 4(sp)
    nop             # Pipeline: load-use hazard
    lw      s2, 8(sp)
    nop             # Pipeline: load-use hazard
    lw      s1, 12(sp)
    nop             # Pipeline: load-use hazard
    lw      s0, 16(sp)
    nop             # Pipeline: load-use hazard
    lw      ra, 20(sp)
    addi    sp, sp, 24
    ret


popcount:
    li      t0, 0 # count = 0
    mv      t1, a0     # n(t1)
popcount_loop:
    beqz    t1, popcount_done
    andi    t2, t1, 1
    add     t0, t0, t2
    srli    t1, t1, 1
    jal     x0, popcount_loop

popcount_done:
    mv      a0, t0
    ret


branchless_clz:
    mv      t0, a0           # input x
    li      a0, 0            # count

    # Branchless CLZ - optimized for pipeline
    srli    t1, t0, 16
    sltiu   t2, t1, 1     # t2 = (t1 == 0) ? 1 : 0
    nop                   # Pipeline: avoid data hazard
    neg     t2, t2        # t2 = (t1 == 0) ? -1 : 0, -1(0xFFFF FFFF)
    li      t1, 16
    nop                   # Pipeline: avoid data hazard
    and     t2, t2, t1    # t2 = (t1 == 0) ? 16 : 0
    add     a0, a0, t2    # -1 (0xFFFF FFFF) = 16
    nop                   # Pipeline: avoid data hazard
    sll     t0, t0, t2

    srli    t1, t0, 24
    sltiu   t2, t1, 1
    nop                   # Pipeline: avoid data hazard
    neg     t2, t2
    li      t1, 8
    nop                   # Pipeline: avoid data hazard
    and     t2, t2, t1
    add     a0, a0, t2
    nop                   # Pipeline: avoid data hazard
    sll     t0, t0, t2

    srli    t1, t0, 28
    sltiu   t2, t1, 1
    nop                   # Pipeline: avoid data hazard
    neg     t2, t2
    li      t1, 4
    nop                   # Pipeline: avoid data hazard
    and     t2, t2, t1
    add     a0, a0, t2
    nop                   # Pipeline: avoid data hazard
    sll     t0, t0, t2

    srli    t1, t0, 30
    sltiu   t2, t1, 1
    nop                   # Pipeline: avoid data hazard
    neg     t2, t2
    li      t1, 2
    nop                   # Pipeline: avoid data hazard
    and     t2, t2, t1
    add     a0, a0, t2
    nop                   # Pipeline: avoid data hazard
    sll     t0, t0, t2

    srli    t1, t0, 31
    sltiu   t2, t1, 1
    nop                   # Pipeline: avoid data hazard
    add     a0, a0, t2

    ret
