# Model Training Guide

This project provides a pipeline for training optimized models using a Teacher-Student knowledge distillation approach. The process involves training a high-performance teacher model and then distilling its knowledge into a more efficient student model.

---

## 1. Prerequisites
Ensure you have Python installed (3.8+ recommended) and the required libraries:

```bash
pip install silabs-mltk audiomentations noisereduce pyloudnorm librosa tensorflow scikit-learn tensorflow-model-optimization
```

---

## 2. Workspace Setup
To use these files in a cloud environment (e.g., Databricks):

1.  **Upload to Workspace**: Upload both `custom_model.py` and `run_custom_model.ipynb` to your Databricks Workspace (e.g., in your `/Users/<your-email>/` folder).

2.  **Unity Catalog Volumes**: Ensure your training data is uploaded to a Unity Catalog Volume.

3.  **Environment Sync**: Run `dbutils.library.restartPython()` in the notebook to ensure all libraries are correctly loaded.

---

## 3. Configuration
Before training, you must update the path placeholders in both files.

### Edit `custom_model.py`
Modify the global path variables at the top of the script:

1.  **`WORKSPACE_MODELS_DIR`** (Line 35): The base directory for all training outputs.
    ```python
    WORKSPACE_MODELS_DIR = "<YOUR_WORKSPACE_DIR>/models"
    ```
2.  **`Teacher_H5`** (Line 37): The specific path for the teacher model artifact. 
    ```python
    Teacher_H5 = f"{WORKSPACE_MODELS_DIR}/custom_model_teacher.h5"
    ```
3.  **`DataRoot`** (Line 40): The absolute path to your dataset in Unity Catalog Volumes.
    ```python
    DataRoot = "<PATH_TO_VOLUMES_DATASET>"
    ```

### Edit `run_custom_model.ipynb`
Modify:

1.  **`sys.path`** (Cell 2): Point to the directory containing `custom_model.py`.
    ```python
    sys.path.append("<PATH_TO_DIRECTORY>")
    ```
2.  **`dst_dir`** (Cell 13): The destination for exported model artifacts.
    ```python
    dst_dir = "<PATH_TO_WORKSPACE_FILES>/models"
    ```

---

## 4. Preprocessing
In the provided pipeline, we have used **Vosk** (Cell 7) as a refinement step to remove false positives. However, you can replace this with any other preprocessing technique or skip this cell based on your specific requirements:

*   **MODEL_PATH**: Path to your refinement model.

    ```python
    MODEL_PATH = "<PATH_TO_ML_LAYER_MODEL>"
    ```

*   **AUDIO_PATH**: Path to your raw audio volume.

    ```python
    AUDIO_PATH = "<PATH_TO_VOLUMES_DATASET>"
    ```

*   **auto_rename**: Set to `True` to automatically update files and metadata in Unity Catalog.

---

## 5. Training Parameters
You can fine-tune the training behavior in `custom_model.py`:

*   **Epochs**: Default is set to `2`. Increase `my_model.epochs` (Line 62).
*   **Batch Size**: `my_model.batch_size` (Line 63).
*   **Dataset Split**: Adjust `test_fraction` inside `MyDataset.load_dataset` (Line 420).
    *   Example: `test_fraction = 0.20` for a fixed 20% validation split.

---

## 6. Training Workflow
The workflow has two phases. **Run all notebook cells in order**.

### Phase 1: Train Teacher Model (Cell 8)
- Sets `os.environ["TRAIN_TEACHER"] = "1"`.
- If a **previous version** (`custom_model_teacher.h5`) exists, training **resumes** (`clean=False`).
- Otherwise, it **starts from scratch** (`clean=True`).
- Accuracy is stored in `/tmp/teacher_accuracy.txt`.

### Phase 2: Train Student Model (Cell 11)
- Sets `os.environ["TRAIN_TEACHER"] = "0"`.
- Uses the latest **teacher model** for knowledge distillation.
- Resumes training if a student model exists.
- Accuracy is stored in `/tmp/student_accuracy.txt`.

---

## 7. Final Artifacts
After training, run the final cell (Cell 13) to locate and copy artifacts:

*   `custom_model.h5`: The trained student model.

*   `custom_model.tflite`: The quantized model for deployment.

*   `custom_model.tflite.summary.txt`: Model profiling summary.

---

### Reference

For further guidance, you can refer to the **examples** folder for a complete sample notebook and script structure ([custom_model.py](../examples/Databricks_Scripts/MLTK_Model_Training/custom_model.py) and [run_custom_model.ipynb](../examples/Databricks_Scripts/MLTK_Model_Training/run_custom_model.ipynb)).