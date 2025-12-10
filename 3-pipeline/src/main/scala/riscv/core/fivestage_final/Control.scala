// SPDX-License-Identifier: MIT
// MyCPU is freely redistributable under the MIT License. See the file
// "LICENSE" for information on usage and redistribution of this file.

package riscv.core.fivestage_final

import chisel3._
import riscv.Parameters

/**
 * Advanced Hazard Detection and Control Unit: Maximum optimization
 *
 * Most sophisticated hazard detection supporting early branch resolution
 * in ID stage with comprehensive forwarding support. Achieves best
 * performance through aggressive optimization.
 *
 * Key Enhancements:
 * - **Early branch resolution**: Branches resolved in ID stage (not EX)
 * - **ID-stage forwarding**: Enables immediate branch operand comparison
 * - **Complex hazard detection**: Handles jump dependencies and multi-stage loads
 *
 * Hazard Types and Resolution:
 * 1. **Control Hazards**:
 *    - Branch taken in ID → flush only IF stage (1 cycle penalty)
 *    - Jump in ID → may need stall if operands not ready
 *
 * 2. **Data Hazards**:
 *    - Load-use for ALU → 1 cycle stall
 *    - Load-use for branch → 1-2 cycle stall depending on stage
 *    - Jump register dependencies → stall until operands ready
 *
 * Complex Scenarios Handled:
 *
 * Scenario 1 - Jump with load dependency:
 * ```
 * LW   x1, 0(x2)   # Load x1
 * JALR x3, x1, 0   # Jump to address in x1 → needs stall
 * ```
 *
 * Scenario 2 - Branch with recent ALU result:
 * ```
 * ADD x1, x2, x3   # Compute x1
 * BEQ x1, x4, label # Branch using x1 → forwarded to ID, no stall
 * ```
 *
 * Performance Impact:
 * - CPI ~1.05-1.2 (best achievable)
 * - Branch penalty reduced to 1 cycle
 * - Minimal stalls through aggressive forwarding
 *
 * @note Most complex control logic but best performance
 * @note Requires ID-stage forwarding paths for full benefit
 */
class Control extends Module {
  val io = IO(new Bundle {
    val jump_flag              = Input(Bool())                                     // id.io.if_jump_flag
    val jump_instruction_id    = Input(Bool())                                     // id.io.ctrl_jump_instruction           //
    val rs1_id                 = Input(UInt(Parameters.PhysicalRegisterAddrWidth)) // id.io.regs_reg1_read_address
    val rs2_id                 = Input(UInt(Parameters.PhysicalRegisterAddrWidth)) // id.io.regs_reg2_read_address
    val memory_read_enable_ex  = Input(Bool())                                     // id2ex.io.output_memory_read_enable
    val rd_ex                  = Input(UInt(Parameters.PhysicalRegisterAddrWidth)) // id2ex.io.output_regs_write_address
    val memory_read_enable_mem = Input(Bool())                                     // ex2mem.io.output_memory_read_enable   //
    val rd_mem                 = Input(UInt(Parameters.PhysicalRegisterAddrWidth)) // ex2mem.io.output_regs_write_address   //

    val if_flush = Output(Bool())
    val id_flush = Output(Bool())
    val pc_stall = Output(Bool())
    val if_stall = Output(Bool())
  })

  // Initialize control signals to default (no stall/flush) state
  io.if_flush := false.B
  io.id_flush := false.B
  io.pc_stall := false.B
  io.if_stall := false.B

  // ============================================================
  // [CA25: Exercise 19] Pipeline Hazard Detection
  // ============================================================
  // Hint: Detect data and control hazards, decide when to insert bubbles
  // or flush the pipeline
  //
  // Hazard types:
  // 1. Load-use hazard: Load result used immediately by next instruction
  // 2. Jump-related hazard: Jump instruction needs register value not ready
  // 3. Control hazard: Branch/jump instruction changes PC
  //
  // Control signals:
  // - pc_stall: Freeze PC (don't fetch next instruction)
  // - if_stall: Freeze IF/ID register (hold current fetch result)
  // - id_flush: Flush ID/EX register (insert NOP bubble)
  // - if_flush: Flush IF/ID register (discard wrong-path instruction)

  // Complex hazard detection for early branch resolution in ID stage
  when(
    // ============ Complex Hazard Detection Logic ============
    // This condition detects multiple hazard scenarios requiring stalls:

    // --- Condition 1: EX stage hazards (1-cycle dependencies) ---
    // TODO: Complete hazard detection conditions
    // Need to detect:
    // 1. Jump instruction in ID stage
    // 2. OR Load instruction in EX stage
    // 3. AND destination register is not x0
    // 4. AND destination register conflicts with ID source registers
    //
    ((io.jump_instruction_id || io.memory_read_enable_ex) && // Either:
      // - Jump in ID needs register value, OR
      // - Load in EX (load-use hazard)
      io.rd_ex =/= 0.U &&                                 // Destination is not x0
      (io.rd_ex === io.rs1_id || io.rd_ex === io.rs2_id)) // Destination matches ID source
    //
    // Examples triggering Condition 1:
    // a) Jump dependency: ADD x1, x2, x3 [EX]; JALR x0, x1, 0 [ID] → stall
    // b) Load-use: LW x1, 0(x2) [EX]; ADD x3, x1, x4 [ID] → stall
    // c) Load-branch: LW x1, 0(x2) [EX]; BEQ x1, x4, label [ID] → stall

      || // OR

        // --- Condition 2: MEM stage load with jump dependency (2-cycle) ---
        // TODO: Complete MEM stage hazard detection
        // Need to detect:
        // 1. Jump instruction in ID stage
        // 2. Load instruction in MEM stage
        // 3. Destination register is not x0
        // 4. Destination register conflicts with ID source registers
        //
        (io.jump_instruction_id &&                              // Jump instruction in ID
          io.memory_read_enable_mem &&                          // Load instruction in MEM
          io.rd_mem =/= 0.U &&                                  // Load destination not x0
          (io.rd_mem === io.rs1_id || io.rd_mem === io.rs2_id)) // Load dest matches jump source
        //
        // Example triggering Condition 2:
        // LW x1, 0(x2) [MEM]; NOP [EX]; JALR x0, x1, 0 [ID]
        // Even with forwarding, load result needs extra cycle to reach ID stage
  ) {
    // Stall action: Insert bubble and freeze pipeline
    // TODO: Which control signals need to be set to insert a bubble?
    // Hint:
    io.id_flush := true.B // - Flush ID/EX register (insert bubble)
    io.pc_stall := true.B // - Freeze PC (don't fetch next instruction)
    io.if_stall := true.B // - Freeze IF/ID (hold current fetch result)

  }.elsewhen(io.jump_flag) {
    // ============ Control Hazard (Branch Taken) ============
    // Branch resolved in ID stage - only 1 cycle penalty
    // Only flush IF stage (not ID) since branch resolved early
    // TODO: Which stage needs to be flushed when branch is taken?
    // Hint: Branch resolved in ID stage, discard wrong-path instruction
    io.if_flush := true.B
    // Note: No ID flush needed - branch already resolved in ID!
    // This is the key optimization: 1-cycle branch penalty vs 2-cycle
  }

  // ============================================================
  // [CA25: Exercise 21] Hazard Detection Summary and Analysis
  // ============================================================
  // Conceptual Exercise: Answer the following questions based on the hazard
  // detection logic implemented above
  //
  // Q1: Why do we need to stall for load-use hazards?
  // Hint: Consider data dependency and forwarding limitations
  // A: Load 指令的資料在 MEM 階段才準備好，但依賴該資料的指令在 EX 階段就需要。
  //    即使有轉發路徑，資料在時間上還沒產生，所以必須 stall 1 週期等待資料就緒。
  //
  //    Load instructions produce data in the MEM stage, but dependent instructions 
  //    need the data in the EX stage. Even with forwarding paths, the data hasn't 
  //    been generated yet in time, so we must stall for 1 cycle to wait for the 
  //    data to be ready.
  //
  // Q2: What is the difference between "stall" and "flush" operations?
  // Hint: Compare their effects on pipeline registers and PC
  // A: Stall 是凍結 pipeline (pc_stall, if_stall) 並插入 bubble(id_flush)，用於等待資料；
  //    Flush 是清空 pipeline 暫存器 (if_flush)，用於丟棄錯誤路徑的指令 (branches/jumps)。
  //
  //    Stall freezes the pipeline (pc_stall, if_stall) and inserts a bubble (id_flush) 
  //    to wait for data. Flush clears pipeline registers (if_flush) to discard 
  //    wrong-path instructions (from branches/jumps).
  //
  // Q3: Why does jump instruction with register dependency need stall?
  // Hint: When is jump target address available?
  // A: JALR 指令需要從暫存器讀取跳躍位址。如果該暫存器的值還在 pipeline 中計算，
  //    必須 stall 直到位址可用(通過轉發或暫存器檔案)。
  //
  //    JALR instructions need to read the jump address from a register. If that 
  //    register's value is still being computed in the pipeline, we must stall 
  //    until the address is available (via forwarding or register file).
  //
  // Q4: In this design, why is branch penalty only 1 cycle instead of 2?
  // Hint: Compare ID-stage vs EX-stage branch resolution
  // A: 分支指令在 ID 階段就完成比較(利用 Exercise 18 ID-stage forwarding)，
  //    只需清空 IF 階段(1 週期)，而不是傳統的清空 IF+ID (2 週期)。
  //
  //    Branch instructions complete comparison in the ID stage (using ID-stage 
  //    forwarding from Exercise 18), only requiring flushing the IF stage (1 cycle), 
  //    instead of the traditional flushing of both IF and ID stages (2 cycles).
  //
  // Q5: What would happen if we removed the hazard detection logic entirely?
  // Hint: Consider data hazards and control flow correctness
  // A: 會發生 Data hazards(讀到錯誤的暫存器值)和 Control hazards(執行錯誤路徑的指令)，
  //    而導致程式計算結果錯誤。
  //
  //    Data hazards (reading incorrect register values) and control hazards 
  //    (executing wrong-path instructions) would occur, causing incorrect program 
  //    computation results.
  //
  // Q6: Complete the stall condition summary:
  // Stall is needed when:
  // 1. EX 階段的 Load-use hazard (或 Jump 指令依賴 EX 階段的資料) (EX stage condition)
  //    Load-use hazard in EX stage (or jump with EX dependency)
  // 2. Jump 指令依賴 MEM 階段的 Load 資料 (MEM stage condition)
  //    Jump instruction with MEM-stage load dependency
  // Flush is needed when:
  // 1. 分支/跳躍發生時 (io.jump_flag = true) (Branch/Jump condition)
  //    Branch/Jump taken (io.jump_flag = true)
  //
}
