# Define minimal required version of CMake.
cmake_minimum_required(VERSION "3.25")

# Project definition
project(
	voice_ble_controller
	VERSION 1.0
	LANGUAGES C CXX ASM
)

# Include the definition of the slc_voice_ble_controller target,
# which contains the content of the SLC project
include(voice_ble_controller.cmake)

set(AIML_APP_DIR "${CMAKE_CURRENT_LIST_DIR}/..")
set(AIML_PKG_DIR "${AIML_APP_DIR}/aiml_sdk")

# Phase 2.3: bring classifier runtime into BLE Micrium app.
target_sources(slc PRIVATE
    "../audio_classifier.cc"
    "../recognize_commands.cc"
    "${AIML_APP_DIR}/autogen/sl_tflite_micro_model.c"
    "${AIML_PKG_DIR}/microfrontend/lib/activity_detection.c"
    "${AIML_PKG_DIR}/microfrontend/lib/activity_detection_util.c"
    "${AIML_PKG_DIR}/microfrontend/lib/dc_notch_filter.c"
    "${AIML_PKG_DIR}/microfrontend/lib/dc_notch_filter_util.c"
    "${AIML_PKG_DIR}/microfrontend/lib/filterbank.c"
    "${AIML_PKG_DIR}/microfrontend/lib/filterbank_util.c"
    "${AIML_PKG_DIR}/microfrontend/lib/frontend.c"
    "${AIML_PKG_DIR}/microfrontend/lib/frontend_util.c"
    "${AIML_PKG_DIR}/microfrontend/lib/log_lut.c"
    "${AIML_PKG_DIR}/microfrontend/lib/log_scale.c"
    "${AIML_PKG_DIR}/microfrontend/lib/log_scale_util.c"
    "${AIML_PKG_DIR}/microfrontend/lib/noise_reduction.c"
    "${AIML_PKG_DIR}/microfrontend/lib/noise_reduction_util.c"
    "${AIML_PKG_DIR}/microfrontend/lib/pcan_gain_control.c"
    "${AIML_PKG_DIR}/microfrontend/lib/pcan_gain_control_util.c"
    "${AIML_PKG_DIR}/microfrontend/lib/window.c"
    "${AIML_PKG_DIR}/microfrontend/lib/window_util.c"
    "${AIML_PKG_DIR}/src/dsp/sl_ml_fft.cc"
    "${AIML_PKG_DIR}/src/features/audio/sl_ml_audio_feature_generation.c"
    "${AIML_PKG_DIR}/src/features/audio/sl_ml_audio_feature_generation_init.c"
    "${AIML_PKG_DIR}/src/tflite/sl_tflite_micro_init.cc"
    "${AIML_PKG_DIR}/src/utils/debug_log.cc"
    # MVP-accelerated TFLM kernels
    "${AIML_PKG_DIR}/src/kernels/mvp1/add.cc"
    "${AIML_PKG_DIR}/src/kernels/mvp1/conv.cc"
    "${AIML_PKG_DIR}/src/kernels/mvp1/depthwise_conv.cc"
    "${AIML_PKG_DIR}/src/kernels/mvp1/fully_connected.cc"
    "${AIML_PKG_DIR}/src/kernels/mvp1/mul.cc"
    "${AIML_PKG_DIR}/src/kernels/mvp1/pooling.cc"
    "${AIML_PKG_DIR}/src/kernels/mvp1/transpose_conv.cc"
    # CMSIS-NN TFLM kernels
    "${AIML_PKG_DIR}/third_party/tflite-micro/tensorflow/lite/micro/kernels/cmsis_nn/softmax.cc"
    "${AIML_PKG_DIR}/third_party/tflite-micro/tensorflow/lite/micro/kernels/cmsis_nn/svdf.cc"
    "${AIML_PKG_DIR}/third_party/tflite-micro/tensorflow/lite/micro/kernels/cmsis_nn/unidirectional_sequence_lstm.cc"
    # MVP driver
    "${SDK_PATH}/compute/driver/mvp/src/sl_mvp.c"
    "${SDK_PATH}/compute/driver/mvp/src/sl_mvp_hal_efr32.c"
    "${SDK_PATH}/compute/driver/mvp/src/sl_mvp_program_area.c"
    "${SDK_PATH}/compute/driver/mvp/src/sl_mvp_util.c"
    # MVP math
    "${SDK_PATH}/compute/math/mvp/src/sl_math_mvp_complex_matrix_mult.c"
    "${SDK_PATH}/compute/math/mvp/src/sl_math_mvp_complex_vector_conjugate.c"
    "${SDK_PATH}/compute/math/mvp/src/sl_math_mvp_complex_vector_dot_product.c"
    "${SDK_PATH}/compute/math/mvp/src/sl_math_mvp_complex_vector_magnitude_squared.c"
    "${SDK_PATH}/compute/math/mvp/src/sl_math_mvp_complex_vector_mult.c"
    "${SDK_PATH}/compute/math/mvp/src/sl_math_mvp_matrix_add.c"
    "${SDK_PATH}/compute/math/mvp/src/sl_math_mvp_matrix_mult.c"
    "${SDK_PATH}/compute/math/mvp/src/sl_math_mvp_matrix_scale.c"
    "${SDK_PATH}/compute/math/mvp/src/sl_math_mvp_matrix_sub.c"
    "${SDK_PATH}/compute/math/mvp/src/sl_math_mvp_matrix_transpose.c"
    "${SDK_PATH}/compute/math/mvp/src/sl_math_mvp_matrix_vector_mult.c"
    "${SDK_PATH}/compute/math/mvp/src/sl_math_mvp_util.c"
    "${SDK_PATH}/compute/math/mvp/src/sl_math_mvp_vector_abs.c"
    "${SDK_PATH}/compute/math/mvp/src/sl_math_mvp_vector_add.c"
    "${SDK_PATH}/compute/math/mvp/src/sl_math_mvp_vector_clamp.c"
    "${SDK_PATH}/compute/math/mvp/src/sl_math_mvp_vector_clip.c"
    "${SDK_PATH}/compute/math/mvp/src/sl_math_mvp_vector_copy.c"
    "${SDK_PATH}/compute/math/mvp/src/sl_math_mvp_vector_dot_product.c"
    "${SDK_PATH}/compute/math/mvp/src/sl_math_mvp_vector_fill.c"
    "${SDK_PATH}/compute/math/mvp/src/sl_math_mvp_vector_mult.c"
    "${SDK_PATH}/compute/math/mvp/src/sl_math_mvp_vector_negate.c"
    "${SDK_PATH}/compute/math/mvp/src/sl_math_mvp_vector_offset.c"
    "${SDK_PATH}/compute/math/mvp/src/sl_math_mvp_vector_scale.c"
    "${SDK_PATH}/compute/math/mvp/src/sl_math_mvp_vector_sub.c"
    "${SDK_PATH}/compute/math/src/sl_math_matrix.c"
    # MVP NN
    "${SDK_PATH}/compute/nn/mvp/src/sl_mvp_ml_add.c"
    "${SDK_PATH}/compute/nn/mvp/src/sl_mvp_ml_conv2d.c"
    "${SDK_PATH}/compute/nn/mvp/src/sl_mvp_ml_depthwise_conv2d.c"
    "${SDK_PATH}/compute/nn/mvp/src/sl_mvp_ml_fully_connected.c"
    "${SDK_PATH}/compute/nn/mvp/src/sl_mvp_ml_mul.c"
    "${SDK_PATH}/compute/nn/mvp/src/sl_mvp_ml_pooling.c"
    "${SDK_PATH}/compute/nn/mvp/src/sl_mvp_ml_transpose_conv2d.c"
    "${SDK_PATH}/compute/nn/mvp/src/sli_mvp_ml_depthwise_conv2d.cc"
    "${SDK_PATH}/compute/nn/mvp/src/sli_mvp_ml_depthwise_conv2d_opt.c"
    "${SDK_PATH}/compute/nn/src/sl_nn_util.c"
    "${SDK_PATH}/compute/util/src/sl_compute_util.c"
    # Board drivers
    "${SDK_PATH}/board_drivers/hardware/driver/mic/src/sl_mic_i2s.c"
    "${SDK_PATH}/platform_core/platform/peripheral/src/sl_hal_usart.c"
    "${SDK_PATH}/platform_core/platform/emlib/src/em_usart.c"
    # LED driver
    "${SDK_PATH}/platform_core/platform/driver/leddrv/src/sl_led.c"
    "${SDK_PATH}/platform_core/platform/driver/leddrv/src/sl_simple_led.c"
    "../autogen/sl_simple_led_instances.c"
)

target_include_directories(slc PUBLIC
    "${AIML_APP_DIR}/autogen"
    "${AIML_APP_DIR}/config"
    "${AIML_PKG_DIR}/config/features/audio"
    "${AIML_PKG_DIR}/config/tflite"
    "${AIML_PKG_DIR}"
    "${AIML_PKG_DIR}/inc/features/audio"
    "${AIML_PKG_DIR}/inc/tflite"
    "${AIML_PKG_DIR}/third_party/flatbuffers/include"
    "${AIML_PKG_DIR}/third_party/gemmlowp"
    "${AIML_PKG_DIR}/third_party/ruy"
    "${AIML_PKG_DIR}/third_party/tflite-micro"
    "${SDK_PATH}/board_drivers/hardware/driver/mic/inc"
    "${SDK_PATH}/platform_core/platform/peripheral/inc"
    "${SDK_PATH}/platform_core/platform/emlib/inc"
    "${SDK_PATH}/cmsis_dsp/Include"
    "${SDK_PATH}/cmsis_dsp/Include/dsp"
    "${SDK_PATH}/cmsis_nn"
    "${SDK_PATH}/cmsis_nn/Include"
    "${SDK_PATH}/compute/driver/mvp/inc"
    "${SDK_PATH}/compute/math/inc"
    "${SDK_PATH}/compute/math/mvp/inc"
    "${SDK_PATH}/compute/nn/mvp/inc"
    "${SDK_PATH}/compute/nn/inc"
    "${SDK_PATH}/compute/util/inc"
    "${SDK_PATH}/platform_core/platform/driver/leddrv/inc"
)

target_compile_definitions(slc PUBLIC
    "TF_LITE_STATIC_MEMORY=1"
    "TF_LITE_MCU_DEBUG_LOG=1"
    "CMSIS_NN=1"
    "SL_CATALOG_TFLITE_MICRO_PRESENT=1"
)

target_compile_options(slc PUBLIC
    $<$<COMPILE_LANGUAGE:C>:-mfp16-format=ieee>
    $<$<COMPILE_LANGUAGE:CXX>:-mfp16-format=ieee>
)

target_link_libraries(slc PUBLIC
    "${AIML_PKG_DIR}/lib/gcc/cortex-m33/libtflm.a"
    "${SDK_PATH}/cmsis_dsp/lib/gcc/cortex-m33/libCMSISDSP.a"
    "${SDK_PATH}/cmsis_nn/lib/gcc/cortex-m33/libcmsis-nn.a"
    "stdc++"
    "m"
)

add_executable(voice_ble_controller
    # Add additional sources here
)

target_include_directories(voice_ble_controller PUBLIC
    # Add additional include paths here
)

target_compile_definitions(voice_ble_controller PUBLIC
    # Add additional macros here
)

target_compile_options(voice_ble_controller PUBLIC
    # Set additional compiler flags here
)

target_link_options(voice_ble_controller PUBLIC
    # Set additional linker flags here
)

# Link with the content defined in the SLC project
target_link_libraries(voice_ble_controller PRIVATE
    slc
)

# Include managed project content if available
include(voice_ble_controller_project.cmake OPTIONAL RESULT_VARIABLE managed_project)
if(managed_project)
    message(STATUS "Using managed project content from ${managed_project}")
endif()

# Force the gcc linker command
set_target_properties(voice_ble_controller PROPERTIES LINKER_LANGUAGE C)

# Create .bin, .hex and .s37 artifacts after building the project
add_custom_command(TARGET voice_ble_controller
    POST_BUILD
    COMMAND ${CMAKE_OBJCOPY} ${OBJCOPY_SREC_CMD} "$<TARGET_FILE:voice_ble_controller>" "$<TARGET_FILE_DIR:voice_ble_controller>/$<TARGET_FILE_BASE_NAME:voice_ble_controller>.s37"
    COMMAND ${CMAKE_OBJCOPY} ${OBJCOPY_IHEX_CMD} "$<TARGET_FILE:voice_ble_controller>" "$<TARGET_FILE_DIR:voice_ble_controller>/$<TARGET_FILE_BASE_NAME:voice_ble_controller>.hex"
    COMMAND ${CMAKE_OBJCOPY} ${OBJCOPY_BIN_CMD}  "$<TARGET_FILE:voice_ble_controller>" "$<TARGET_FILE_DIR:voice_ble_controller>/$<TARGET_FILE_BASE_NAME:voice_ble_controller>.bin" 
)

# Run post-build pipeline to perform additional post-processing
if(post_build_command)
add_custom_command(TARGET voice_ble_controller
    POST_BUILD
    WORKING_DIRECTORY ${CMAKE_CURRENT_LIST_DIR}/..
    COMMAND ${post_build_command}
)
endif()