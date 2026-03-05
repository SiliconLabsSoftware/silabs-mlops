"""
Silicon Labs NPU Model Profiling
------------------------------------------------
This shows you how to use the 'model' module to profile
TFLite models for Silicon Labs hardware.
"""

from silabs_mlops import model

# 1. Basic Path Setup
# Change this to your actual .tflite model path
model_path = "workspace/outputs/my_model.tflite" 

# =========================================================
# USE CASE A: Local Simulation (No Hardware Required)
# =========================================================
# Use this when you want to check model metrics on your PC.
print("\n--- [A] Local Simulation Mode ---")
try:
    result = model.profile(
        model_path=model_path,
        use_simulator=True,          # RUN LOCALLY ON PC
        output_dir="./local_profile"
    )
    # The result object contains all the extracted data:
    print(f"  ✓ Model:      {result.model_name}")
    print(f"  ✓ Arena Size: {result.arena_size_kb:.1f} KB")
    print(f"  ✓ Total MACs: {result.total_macs:,}")
    print(f"  ✓ Board:      {result.board}")
    print(f"  ✓ Saved to:   {result.output_dir}")
except Exception as e:
    print(f"  [!] Simulation failed: {e}")


# =========================================================
# USE CASE B: Real Hardware Profiling
# =========================================================
# Uncomment the block below if a SiLabs Board is connected via USB.
# ---------------------------------------------------------
# print("\n--- [B] Real Hardware Profiling ---")
# try:
#     result = model.profile(
#         model_path=model_path,
#         device_id="440339411",         # OPTIONAL: J-Link Serial Number
#         accelerator="mvpv1",           # OPTIONAL: Target NPU version
#         platform="brd2605",            # OPTIONAL: Specific Dev Kit
#         weights_paging=False,          # OPTIONAL: Enable for large models
#         timeout=600                    # OPTIONAL: Max seconds to wait
#     )
#     print(f"  ✓ Hardware Arena Size: {result.arena_size_kb:.1f} KB")
#     print(f"  ✓ Hardware Total MACs: {result.total_macs:,}")
# except Exception as e:
#     print(f"  [!] Hardware profiling failed: {e}")


# =========================================================
# USE CASE C: Launching the Web GUI Dashboard
# =========================================================
# Opens the interactive Profiler dashboard in your browser.
# ---------------------------------------------------------
# print("\n--- [C] Visual Dashboard ---")
# model.profile(model_path=model_path, gui=True)


# =========================================================
# USE CASE D: Explicit Path to Toolkit
# =========================================================
# Use if the toolkit is NOT in your Windows PATH.
# ---------------------------------------------------------
# print("\n--- [D] Custom Toolkit Path ---")
# model.profile(
#     model_path=model_path,
#     profiler_path=r"C:\SimplicityStudio\v5\adapter_packs\ml\mvp_profiler.exe"
# )
