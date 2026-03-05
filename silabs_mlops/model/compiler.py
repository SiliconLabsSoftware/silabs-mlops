"""
Compiler utilities for converting TensorFlow/Keras models into TFLite files.
"""
import tensorflow as tf
import numpy as np
import os
from pathlib import Path
from typing import Optional, Callable, Union, List

class TFLiteCompiler:
    """
    Compiler for converting TensorFlow/Keras models to TFLite.
    Optimized for Silicon Labs MCUs with automated INT8 quantization.
    """
    
    def _get_synthetic_representative_dataset(self, converter):
        """Generates a synthetic representative dataset based on model input shapes."""
        # Get model signatures to find input shapes
        try:
            # For Keras models
            model_inputs = converter._keras_model.inputs
            # Store (shape, dtype_object)
            input_info = [(i.shape, tf.as_dtype(i.dtype)) for i in model_inputs]
        except Exception:
            input_info = None

        def representative_dataset_gen():
            for _ in range(100):
                if input_info:
                    samples = []
                    for shape, dtype_obj in input_info:
                        # Handle variable batch dimensions by using 1
                        effective_shape = [1 if d is None else d for d in shape]
                        # Create synthetic data matching the dtype
                        if dtype_obj.is_floating:
                            sample = np.random.uniform(-1, 1, effective_shape).astype(dtype_obj.as_numpy_dtype)
                        else:
                            # For integer types
                            sample = np.random.randint(0, 255, effective_shape).astype(dtype_obj.as_numpy_dtype)
                        samples.append(sample)
                    yield samples
                else:
                    # Generic fallback
                    yield [np.random.uniform(-1, 1, (1, 224, 224, 3)).astype(np.float32)]

        return representative_dataset_gen

    def compile(
        self, 
        model: Union[tf.keras.Model, str], 
        output_path: str,
        optimize_for_size: bool = True,
        representative_dataset: Optional[Callable] = None
    ) -> str:
        """
        Convert a model to .tflite format with robust quantization and safety checks.
        """
        model_path = None
        if isinstance(model, str):
            model_path = Path(model)
            if not model_path.exists():
                raise FileNotFoundError(f"Model path not found: {model}")

        # Determine Output Path
        out_p = Path(output_path)
        if out_p.is_dir():
            print(f"NOTE: Output path is a directory. Saving as: {out_p}/model_optimized.tflite")
            out_p = out_p / "model_optimized.tflite"
        elif not out_p.suffix == ".tflite":
            out_p = out_p.with_suffix(".tflite")
        
        out_p.parent.mkdir(parents=True, exist_ok=True)

        # Select Converter & Safe Detection
        try:
            if model_path:
                if model_path.is_dir():
                    # Safer SavedModel Detection
                    if (model_path / "saved_model.pb").exists():
                        print(f"Detected SavedModel directory: {model_path}")
                        converter = tf.lite.TFLiteConverter.from_saved_model(str(model_path))
                    else:
                        raise ValueError(f"Directory {model_path} is missing 'saved_model.pb'. Not a valid SavedModel.")
                elif model_path.suffix in ['.h5', '.keras']:
                    print(f"Loading Keras file: {model_path}")
                    # Use compile=False to avoid serialization issues with metrics/optimizers
                    keras_model = tf.keras.models.load_model(str(model_path), compile=False)
                    converter = tf.lite.TFLiteConverter.from_keras_model(keras_model)
                else:
                    raise ValueError(f"Unsupported file format: {model_path.suffix}. Use .h5, .keras, or a SavedModel directory.")
            else:
                # Direct Keras object
                converter = tf.lite.TFLiteConverter.from_keras_model(model)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize TFLite Converter: {e}. "
                               f"(Using TF version {tf.__version__})")

        # Apply Quantization Strategy (MCU Optimized)
        print("Applying Silicon Labs recommended quantization settings...")
        converter.optimizations = [tf.lite.Optimize.DEFAULT]
        
        # Determine Representative Dataset
        rep_gen = representative_dataset
        if not rep_gen:
            print("WARNING: No representative dataset provided. Generating synthetic calibration data...")
            print("NOTE: For final production, using real representative data is highly recommended for accuracy.")
            rep_gen = self._get_synthetic_representative_dataset(converter)

        # Attempt INT8 conversion
        try:
            print("Attempting Full Integer Quantization (INT8)...")
            converter.representative_dataset = rep_gen
            converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
            converter.inference_input_type = tf.int8
            converter.inference_output_type = tf.int8
            tflite_model = converter.convert()
            final_suffix = "_int8"
        except Exception as e:
            print(f"INT8 conversion failed: {e}")
            print("FALLING BACK: Continuous Dynamic Range quantization...")
            # Reset and try fallback
            converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS]
            converter.inference_input_type = tf.float32
            converter.inference_output_type = tf.float32
            tflite_model = converter.convert()
            final_suffix = "_dynamic"

        # Update filename if it was a generic one or directory-based
        if "_optimized" in out_p.name:
            out_p = out_p.with_name(out_p.stem.replace("_optimized", final_suffix) + ".tflite")

        with open(out_p, 'wb') as f:
            f.write(tflite_model)
            
        print(f"SUCCESS: Model compiled to {out_p} ({len(tflite_model)/1024:.1f} KB)")
        return str(out_p.absolute())

