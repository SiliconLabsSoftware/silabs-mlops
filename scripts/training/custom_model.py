"""
Audio Classification: Teacher–Student Training
- Trains a teacher CNN and a distilled student CNN on .wav data
- Uses MLTK AudioFeatureGenerator + augmentations
- Stratified train/validation split
- TFLite INT8 conversion
Edit placeholders before running:
  WORKSPACE_MODELS_DIR = "Path to where you want models saved"
  DATA_ROOT = "Path to your volumes dataset"
"""

import os
import re
import warnings
import logging
import pandas as pd
import soundfile as sf
from glob import glob
from sklearn.model_selection import train_test_split
import numpy as np
import tensorflow as tf
import mltk.core as mltk_core
from mltk.core.preprocess.audio.audio_feature_generator import (
    AudioFeatureGeneratorSettings,
)
from mltk.core.preprocess.utils import tf_dataset as tf_dataset_utils
from mltk.core.preprocess.utils import audio as audio_utils
from mltk.utils.python import install_pip_package
from mltk.core.keras.models import KnowledgeDistillationModel

WORKSPACE_MODELS_DIR = "<YOUR_WORKSPACE_DIR>/models"

Teacher_H5 = f"{WORKSPACE_MODELS_DIR}/custom_model_teacher.h5"


DataRoot = "<PATH_TO_VOLUMES_DATASET>"


# ---------------------------------------------------------------------
# MLTK model definition
# ---------------------------------------------------------------------
class MyModel(
    mltk_core.MltkModel,
    mltk_core.TrainMixin,
    mltk_core.DatasetMixin,
    mltk_core.EvaluateClassifierMixin,
    mltk_core.SshMixin,
):
    pass


my_model = MyModel()

# General Settings
my_model.version = 2
my_model.description = "custom model"

# Training Basic Settings
my_model.epochs = 2
my_model.batch_size = 32

# ---------------------------------------------------------------------
# Model architectures
# ---------------------------------------------------------------------


# Build teacher model
def my_teacher_model_builder(model: MyModel) -> tf.keras.Model:
    input_shape = model.input_shape
    filters = 48

    keras_model = tf.keras.models.Sequential(name=model.name + "-teacher")
    keras_model.add(
        tf.keras.layers.Conv2D(filters, (3, 3), padding="same", input_shape=input_shape)
    )
    keras_model.add(tf.keras.layers.BatchNormalization())
    keras_model.add(tf.keras.layers.Activation("relu"))
    keras_model.add(tf.keras.layers.MaxPooling2D(2, 2))

    keras_model.add(tf.keras.layers.Conv2D(filters * 2, (3, 3), padding="same"))
    keras_model.add(tf.keras.layers.BatchNormalization())
    keras_model.add(tf.keras.layers.Activation("relu"))
    keras_model.add(tf.keras.layers.MaxPooling2D(2, 2))

    keras_model.add(tf.keras.layers.Conv2D(filters * 4, (3, 3), padding="same"))
    keras_model.add(tf.keras.layers.BatchNormalization())
    keras_model.add(tf.keras.layers.Activation("relu"))
    keras_model.add(tf.keras.layers.MaxPooling2D(2, 2))

    keras_model.add(tf.keras.layers.Conv2D(filters * 4, (3, 3), padding="same"))
    keras_model.add(tf.keras.layers.BatchNormalization())
    keras_model.add(tf.keras.layers.Activation("relu"))
    keras_model.add(tf.keras.layers.MaxPooling2D(2, 2))

    keras_model.add(tf.keras.layers.Conv2D(filters * 4, (3, 3), padding="same"))
    keras_model.add(tf.keras.layers.BatchNormalization())
    keras_model.add(tf.keras.layers.Activation("relu"))
    keras_model.add(
        tf.keras.layers.MaxPooling2D(
            pool_size=(keras_model.layers[-1].output_shape[1], 1)
        )
    )

    keras_model.add(tf.keras.layers.Dropout(0.5))
    keras_model.add(tf.keras.layers.Flatten())
    keras_model.add(tf.keras.layers.Dense(model.n_classes, activation="softmax"))

    keras_model.compile(
        loss="categorical_crossentropy",
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
        metrics=["accuracy"],
    )
    return keras_model


# Save teacher model
def my_teacher_model_saver(
    mltk_model: mltk_core.MltkModel, keras_model: tf.keras.Model, logger: logging.Logger
) -> tf.keras.Model:
    logger.info(f"Saving teacher model to {Teacher_H5}")
    # Ensure directory exists
    os.makedirs(os.path.dirname(Teacher_H5), exist_ok=True)
    keras_model.save(Teacher_H5)
    return keras_model


# Build student model
def my_student_model_builder(model: MyModel) -> tf.keras.Model:
    input_shape = model.input_shape
    filters = 10

    keras_model = tf.keras.models.Sequential(name=model.name + "-student")
    keras_model.add(
        tf.keras.layers.Conv2D(filters, (3, 3), padding="same", input_shape=input_shape)
    )
    keras_model.add(tf.keras.layers.BatchNormalization())
    keras_model.add(tf.keras.layers.Activation("relu"))
    keras_model.add(tf.keras.layers.MaxPooling2D(2, 2))

    keras_model.add(tf.keras.layers.Conv2D(filters * 2, (3, 3), padding="same"))
    keras_model.add(tf.keras.layers.BatchNormalization())
    keras_model.add(tf.keras.layers.Activation("relu"))
    keras_model.add(tf.keras.layers.MaxPooling2D(2, 2))

    keras_model.add(tf.keras.layers.Conv2D(filters * 4, (3, 3), padding="same"))
    keras_model.add(tf.keras.layers.BatchNormalization())
    keras_model.add(tf.keras.layers.Activation("relu"))
    keras_model.add(tf.keras.layers.MaxPooling2D(2, 2))

    keras_model.add(tf.keras.layers.Conv2D(filters * 4, (3, 3), padding="same"))
    keras_model.add(tf.keras.layers.BatchNormalization())
    keras_model.add(tf.keras.layers.Activation("relu"))
    keras_model.add(tf.keras.layers.MaxPooling2D(2, 2))

    keras_model.add(tf.keras.layers.Conv2D(filters * 2, (3, 3), padding="same"))
    keras_model.add(tf.keras.layers.BatchNormalization())
    keras_model.add(tf.keras.layers.Activation("relu"))
    keras_model.add(
        tf.keras.layers.MaxPooling2D(
            pool_size=(keras_model.layers[-1].output_shape[1], 1)
        )
    )

    keras_model.add(tf.keras.layers.Dropout(0.3))
    keras_model.add(tf.keras.layers.Flatten())
    keras_model.add(tf.keras.layers.Dense(model.n_classes, activation="softmax"))

    keras_model.compile(
        loss="categorical_crossentropy", optimizer="adam", metrics=["accuracy"]
    )

    # Load the previously saved "teacher" keras model
    if not os.path.exists(Teacher_H5):
        raise FileNotFoundError(
            f"Teacher model not found at {Teacher_H5}. Train teacher first."
        )
    teacher_model = tf.keras.models.load_model(Teacher_H5, compile=True)

    distiller = KnowledgeDistillationModel(student=keras_model, teacher=teacher_model)
    distiller.compile(
        optimizer="adam",
        metrics=["accuracy"],
        student_loss_fn=tf.keras.losses.CategoricalCrossentropy(),
        distillation_loss_fn=tf.keras.losses.KLDivergence(),
        alpha=0.1,
        temperature=10,
    )
    return distiller


# Save student model
def my_student_model_saver(
    mltk_model: mltk_core.MltkModel, keras_model: tf.keras.Model, logger: logging.Logger
) -> tf.keras.Model:
    """After KD training, return the student network only."""
    return keras_model.student if hasattr(keras_model, "student") else keras_model


# ---------------------------------------------------------------------
# Callbacks / training controls
# (will be overridden appropriately in prepare_teacher_or_student_model)
# ---------------------------------------------------------------------
my_model.checkpoint["monitor"] = "val_accuracy"

my_model.reduce_lr_on_plateau = dict(
    monitor="accuracy", factor=0.95, patience=1, min_delta=0.01
)

my_model.early_stopping = dict(
    monitor="val_student_loss", mode="min", verbose=1, patience=30, min_delta=0.0001
)

my_model.train_callbacks = [tf.keras.callbacks.TerminateOnNaN()]

# ---------------------------------------------------------------------
# AudioFeatureGenerator Settings
# ---------------------------------------------------------------------
frontend_settings = AudioFeatureGeneratorSettings()
frontend_settings.sample_rate_hz = 16000
frontend_settings.sample_length_ms = 1000
frontend_settings.window_size_ms = 20
frontend_settings.window_step_ms = 10
frontend_settings.filterbank_n_channels = 68
frontend_settings.filterbank_upper_band_limit = frontend_settings.sample_rate_hz / 2
frontend_settings.filterbank_lower_band_limit = 125.0

frontend_settings.noise_reduction_enable = True
frontend_settings.noise_reduction_smoothing_bits = 10
frontend_settings.noise_reduction_even_smoothing = 0.025
frontend_settings.noise_reduction_odd_smoothing = 0.06
frontend_settings.noise_reduction_min_signal_remaining = 0.03

frontend_settings.pcan_enable = False
frontend_settings.log_scale_enable = True
frontend_settings.log_scale_shift = 6
frontend_settings.dc_notch_filter_enable = True
frontend_settings.dc_notch_filter_coefficient = 0.95
frontend_settings.quantize_dynamic_scale_enable = True
frontend_settings.quantize_dynamic_scale_range_db = 40.0

my_model.model_parameters.update(frontend_settings)
height, width = frontend_settings.spectrogram_shape
my_model.input_shape = (height, width, 1)


# ---------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------
def derive_label_from_filename(path: str) -> str:
    base = os.path.basename(path)
    m = re.match(r"([A-Za-z0-9\-]+)_", base)
    if m:
        return m.group(1).lower()
    # fallback: parent directory name
    return os.path.basename(os.path.dirname(path)).lower()


def build_dataframe_from_dir(root_dir: str) -> pd.DataFrame:
    wavs = sorted(glob(os.path.join(root_dir, "*.wav")))
    if not wavs:
        raise FileNotFoundError(f"No WAV files found under {root_dir}.")
    rows = []
    for p in wavs:
        rows.append(
            {
                "file_path": os.path.abspath(p),
                "class_label": derive_label_from_filename(p),
            }
        )
    df = pd.DataFrame(rows).dropna()

    # Drop classes with too few samples
    vc = df["class_label"].value_counts()
    too_small = vc[vc < 2]
    if not too_small.empty:
        print("[WARN] Dropping classes with <2 samples:", dict(too_small))
        df = df[~df["class_label"].isin(too_small.index)].copy()
    return df


# Build GLOBAL_DF from local directory
GLOBAL_DF = build_dataframe_from_dir(DataRoot)

# Derive class list and ensure consistency
my_model.classes = sorted(GLOBAL_DF["class_label"].unique())
NUM_CLASSES = len(my_model.classes)
print("Data root:", DataRoot)
print("Classes:", my_model.classes)
print("Total samples:", len(GLOBAL_DF))

# ---------------------------------------------------------------------
# Audio augmentation pipeline
# ---------------------------------------------------------------------
# Ensure these packages are installed in your environment
install_pip_package("audiomentations")
install_pip_package("noisereduce")
install_pip_package("pyloudnorm")

import librosa
import audiomentations
import noisereduce
import pyloudnorm


def safe_load_wav(path: str):
    """
    Prefer soundfile; fallback to librosa.
    Returns (audio: float32 mono, sr: int)
    """
    try:
        data, sr = sf.read(path, always_2d=False)
        if data.ndim > 1:
            data = librosa.to_mono(data.T)
        return data.astype(np.float32), sr
    except Exception:
        data, sr = librosa.load(path, sr=None, mono=True)
        return data.astype(np.float32), sr


def audio_augmentation_pipeline(
    path_batch: np.ndarray, label_batch: np.ndarray, seed: np.ndarray
) -> np.ndarray:
    batch_length = path_batch.shape[0]
    height, width = frontend_settings.spectrogram_shape
    x_batch = np.empty((batch_length, height, width, 1), dtype=np.int8)

    padding_length_ms = 1000
    padded_frontend = frontend_settings.copy()
    padded_frontend.sample_length_ms += padding_length_ms

    # Global augmentation instance
    aug = globals().get("audio_augmentations", None)
    if aug is None:
        aug = audiomentations.Compose(
            p=1.0,
            transforms=[
                audiomentations.TimeStretch(min_rate=0.90, max_rate=1.10, p=1.0),
                audiomentations.Gain(min_gain_db=0.95, max_gain_db=1.50, p=1.0),
                audiomentations.AddGaussianSNR(min_snr_db=30, max_snr_db=60, p=0.25),
            ],
        )
        globals()["audio_augmentations"] = aug

    for i, (audio_path, _) in enumerate(zip(path_batch, label_batch)):
        try:
            # Ensure string path
            if isinstance(audio_path, (bytes, bytearray, np.bytes_)):
                audio_path = audio_path.decode("utf-8")
            audio_path = str(audio_path)
            np.random.seed(
                int(seed[i].numpy() if hasattr(seed[i], "numpy") else seed[i])
            )

            # Load audio (safe)
            sample, sr = safe_load_wav(audio_path)
            sample = np.clip(sample, -1.0, 1.0)

            # Normalize volume
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                sample = pyloudnorm.normalize.peak(sample, 0.0)

            # Noise reduction
            sample = noisereduce.reduce_noise(y=sample, sr=sr, stationary=True)

            # Fit to 1000ms, then pad left with silence
            out_len = int((sr * frontend_settings.sample_length_ms) / 1000)
            sample = audio_utils.adjust_length(
                sample,
                out_length=out_len,
                trim_threshold_db=30,
                offset=np.random.uniform(0, 1),
            )

            pad_len = int((sr * padding_length_ms) / 1000)
            padded = np.zeros((pad_len + out_len,), dtype=np.float32)
            padded[pad_len : pad_len + len(sample)] = sample

            # Augment
            augmented = aug(padded, sr)

            # Resample if needed
            if sr != frontend_settings.sample_rate_hz:
                augmented, _ = audio_utils.resample(
                    augmented, orig_sr=sr, target_sr=frontend_settings.sample_rate_hz
                )

            # Spectrogram
            augmented = np.clip(augmented, -1.0, 1.0)
            spec = audio_utils.apply_frontend(
                sample=augmented, settings=padded_frontend, dtype=np.int8
            )

            spec = spec[-height:, :]
            spec = np.expand_dims(spec, -1)
            x_batch[i] = spec

        except Exception as e:
            print(f"[WARN] Failed for {audio_path}: {e}")
            x_batch[i] = np.zeros((height, width, 1), dtype=np.int8)

    return x_batch


# ---------------------------------------------------------------------
# Dataset wrapper for MLTK
# ---------------------------------------------------------------------
print("Samples loaded:", len(GLOBAL_DF))
print("Classes:", sorted(GLOBAL_DF["class_label"].unique()))

# Update model classes (must match GLOBAL_DF)
my_model.classes = sorted(GLOBAL_DF["class_label"].unique())


class MyDataset(mltk_core.MltkDataset):
    def __init__(self):
        super().__init__()
        self.pools = []

    def load_dataset(self, subset, **kwargs):
        df = GLOBAL_DF.copy()

        # ✅ Always use fixed 80% train / 20% validation split
        test_fraction = 0.20  # 20% validation

        df_train, df_val = train_test_split(
            df,
            test_size=test_fraction,
            random_state=42,
            stratify=df["class_label"],  # ensures stratified split
        )

        # ✅ Select correct subset
        used = df_train if subset == "training" else df_val

        # Extract features and labels
        x_paths = used["file_path"].tolist()
        y_labels = used["class_label"].tolist()

        # Convert labels → ids → one-hot vectors
        label_to_id = {c: i for i, c in enumerate(my_model.classes)}
        y_ids = [label_to_id[y] for y in y_labels]
        y_onehot = tf.keras.utils.to_categorical(y_ids, num_classes=NUM_CLASSES)

        # Build TF datasets
        x_ds = tf.data.Dataset.from_tensor_slices(x_paths)
        y_ds = tf.data.Dataset.from_tensor_slices(y_onehot)

        # Random seed counter (TF2 compatible)
        seed_counter = tf.data.Dataset.counter()
        x_ds = x_ds.zip((x_ds, y_ds, seed_counter)).batch(my_model.batch_size)

        # Preprocessing / augmentation
        x_ds, pool = tf_dataset_utils.parallel_process(
            x_ds,
            audio_augmentation_pipeline,
            dtype=np.int8,
            n_jobs=0,  # single worker to avoid multiprocessing issues
            name=subset,
        )
        self.pools.append(pool)

        # Final dataset
        ds = tf.data.Dataset.zip((x_ds.unbatch(), y_ds))
        ds = ds.batch(my_model.batch_size).prefetch(2)

        return ds


my_model.dataset = MyDataset()

# Audio classifier metadata (included in .tflite metadata)
my_model.model_parameters["latency_ms"] = 200
my_model.model_parameters["minimum_count"] = 2
my_model.model_parameters["average_window_duration_ms"] = int(
    my_model.model_parameters["latency_ms"]
    * my_model.model_parameters["minimum_count"]
    * 1.1
)
my_model.model_parameters["detection_threshold"] = int(0.65 * 255)
my_model.model_parameters["suppression_ms"] = 900
my_model.model_parameters["volume_gain"] = 0
my_model.model_parameters["verbose_model_output_logs"] = False


# Get teacher h5 path
def get_teacher_h5_path(try_archive=False, check_exists=True) -> str:
    ext = ".teacher.test.h5" if my_model.test_mode_enabled else ".teacher.h5"
    retval = None
    if try_archive:
        try:
            retval = my_model.get_archive_file(f"{my_model.name}{ext}")
        except:
            pass

    if retval is None:
        retval = my_model.model_specification_path.replace(".py", ext)

    if check_exists and not os.path.exists(retval):
        raise RuntimeError(
            f"Teacher keras model not found: {retval}\n"
            "Have you trained the teacher model first?\n"
            "e.g.:\nexport TRAIN_TEACHER=1\n"
        )
    return retval


# Prepare teacher or student model
def prepare_teacher_or_student_model(train_teacher: bool | None = None):
    env_val = os.environ.get("TRAIN_TEACHER", "0")
    print("ENV VAR TRAIN_TEACHER =", env_val)
    if train_teacher is None:
        train_teacher = env_val == "1"

    if not isinstance(my_model.checkpoint, dict):
        my_model.checkpoint = {}

    if train_teacher:
        print("Preparing TEACHER training...")
        my_model.build_model_function = my_teacher_model_builder
        my_model.on_save_keras_model = my_teacher_model_saver

        my_model.checkpoint["monitor"] = "accuracy"
        my_model.checkpoint["mode"] = "max"
        my_model.checkpoint["save_best_only"] = True
        my_model.checkpoint["filepath"] = "teacher-weights.h5"

        my_model.early_stopping = dict(
            monitor="loss", mode="min", patience=10, verbose=1, min_delta=1e-4
        )

        my_model.tflite_converter = None

    else:
        print("Preparing STUDENT training...")
        my_model.build_model_function = my_student_model_builder
        my_model.on_save_keras_model = my_student_model_saver

        my_model.checkpoint["monitor"] = "student_loss"
        my_model.checkpoint["mode"] = "min"
        my_model.checkpoint["save_best_only"] = True
        my_model.checkpoint["filepath"] = "student-weights.h5"

        my_model.early_stopping = dict(
            monitor="student_loss", mode="min", patience=10, verbose=1, min_delta=1e-4
        )

        # TFLite int8 conversion for student
        my_model.tflite_converter["optimizations"] = [tf.lite.Optimize.DEFAULT]
        my_model.tflite_converter["supported_ops"] = [
            tf.lite.OpsSet.TFLITE_BUILTINS_INT8
        ]
        my_model.tflite_converter["inference_input_type"] = np.int8
        my_model.tflite_converter["inference_output_type"] = np.int8
        my_model.tflite_converter["representative_dataset"] = "generate"


# Main
if __name__ == "__main__":
    from mltk import cli

    cli.get_logger(verbose=True)

    test_mode_enabled = False

    # 1) Train the TEACHER
    prepare_teacher_or_student_model(train_teacher=True)
    train_results = mltk_core.train_model(my_model, clean=True, test=test_mode_enabled)
    print(train_results)

    # 2) Train the STUDENT
    prepare_teacher_or_student_model(train_teacher=False)
    train_results = mltk_core.train_model(my_model, clean=True, test=test_mode_enabled)
    print(train_results)

    # 3) Evaluate and profile
    tflite_eval_results = mltk_core.evaluate_model(
        my_model, verbose=True, test=test_mode_enabled
    )
    print(tflite_eval_results)

    profiling_results = mltk_core.profile_model(my_model, test=test_mode_enabled)
    print(profiling_results)
