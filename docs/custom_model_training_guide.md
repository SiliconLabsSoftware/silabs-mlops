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

---

## 3. Configuration
Before training, you must update the path placeholders in both files.

### Edit `custom_model.py`
Modify the global path variables at the top of the script:

1.  **`WORKSPACE_MODELS_DIR`** (Line 35): The base directory for all training outputs.
    ```python
    WORKSPACE_MODELS_DIR = "<YOUR_WORKSPACE_DIR/models>"
    ```
2.  **`Teacher_H5`** (Line 37): The specific path for the teacher model artifact. This is derived from the workspace directory by default.
    ```python
    Teacher_H5 = f"{WORKSPACE_MODELS_DIR}/custom_model_teacher.h5"
    ```
3.  **`DataRoot`** (Line 40): The absolute path to your dataset in Unity Catalog Volumes.
    ```python
 # Example Unity Catalog Volume path:
    DataRoot = "/Volumes/catalog_name/schema_name/volume_name/dataset_folder"    
    ```

### Edit `run_custom_model.ipynb`
Modify:

1.  **`sys.path`** (Cell 2): Point to the Workspace directory containing `custom_model.py`.
2.  **`dst_dir`** (Cell 13): The destination for exported model artifacts.
Eg: dst_dir = "<Path_to_workspace_files/models>"


---

## 4. Training Parameters
You can fine-tune the training behavior in `custom_model.py`:

*   **Epochs**: Default is set to `2` for testing. Increase `my_model.epochs` in `custom_model.py` for full training.
*   **Batch Size**: `my_model.batch_size` (default `32`).
*   **Dataset Split**: Adjust `test_fraction` inside `MyDataset.load_dataset` (Line 423).
    *   Example: `test_fraction = 0.2` for a 20% validation split.

---

## 5. Training Workflow
The workflow has two phases. **Run all notebook cells in order** so the teacher model, student model, and exported artifacts are generated correctly.

### Phase 1: Train Teacher Model
- Sets `os.environ["TRAIN_TEACHER"] = "1"`.
- If a **previous version of the teacher model** exists (a base model), training will **resume / fine‑tune from that version**.
- If no previous version exists, the teacher model is **trained from scratch**.
- Output: `custom_model_teacher.h5`.

### Phase 2: Train Student Model (Knowledge Distillation)
- Sets `os.environ["TRAIN_TEACHER"] = "0"`.
- If a **previous version of the student model** exists, it will **resume / fine‑tune from that version**.
- If no previous student checkpoint exists, the student is **trained from scratch**.
- The student always learns from the **latest fine‑tuned teacher model**.

---

## 6. Final Artifacts
After training, run the final cell to copy:
- `custom_model.h5`: The student model.
- `custom_model.tflite`: The quantized model for deployment.
- `custom_model.tflite.summary.txt`: Profiling summary.

---

### Reference

For further guidance, you can refer to the **examples** folder for a complete sample notebook and script structure ([custom_model.py](../examples/Databricks_Scripts/MLTK_Model_Training/custom_model.py) and [run_custom_model.ipynb](../examples/Databricks_Scripts/MLTK_Model_Training/run_custom_model.ipynb)).