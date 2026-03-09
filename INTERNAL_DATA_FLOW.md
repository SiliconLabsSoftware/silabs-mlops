# Internal Flow Explained - With Code References

This document shows **exactly where each step happens** in the code.

---

## 🔄 Step-by-Step Flow

### **Step 1: User Calls `data.config()`**

**File**: `silabs_mlops/data/__init__.py`

```python
# Line 49-74
def config(
    server_endpoint: str,
    workspace_url: str,
    table_name: str,
    client_id: str,
    client_secret: str
) -> None:
    """Configure your Databricks credentials for data ingestion."""
    global _config
    _config = IngestConfig(  # ← Creates IngestConfig object
        server_endpoint=server_endpoint,
        workspace_url=workspace_url,
        table_name=table_name,
        client_id=client_id,
        client_secret=client_secret
    )
    print("✓ Configuration saved.")
```

**What happens**:
- Creates an `IngestConfig` object (from `silabs_mlops/data/ingest/config.py`)
- Stores it in module-level variable `_config`

---

### **Step 2: User Calls `data.ingest(my_data)`**

**File**: `silabs_mlops/data/__init__.py`

```python
# Line 77-113
def ingest(data: List[Dict[str, Any]]) -> bool:
    """Ingest data to Databricks Delta Lake via ZeroBus."""
    if _config is None:  # ← Check if config() was called
        print("Error: Configuration not set. Call data.config() first.")
        return False
    
    ingestor = DataIngestor(_config)  # ← Creates DataIngestor
    return ingestor.ingest(data=data)  # ← Calls ingestor
```

**What happens**:
- Uses the stored `_config` from Step 1
- Creates a `DataIngestor` object (from `silabs_mlops/data/ingest/ingestor.py`)
- Calls `ingestor.ingest(data=data)`

---

### **Step 3: `DataIngestor` Does the Work**

**File**: `silabs_mlops/data/ingest/ingestor.py`

```python
# Line 18-38 (Constructor)
class DataIngestor:
    def __init__(self, config: IngestConfig):
        """Initialize data ingestor."""
        self.config = config
        self.client = ZerobusIngestClient(  # ← Creates ZerobusIngestClient
            server_endpoint=config.server_endpoint,
            workspace_url=config.workspace_url,
            table_name=config.table_name,
            client_id=config.client_id,
            client_secret=config.client_secret,
        )

# Line 74-98 (Ingest method)
    def ingest(self, data: Optional[List[Dict[str, Any]]] = None, ...) -> bool:
        """Main ingestion workflow."""
        # ... get records ...
        
        try:
            self.client.connect()  # ← Connects to ZeroBus
            self.client.ingest_batch(records)  # ← Sends data
            return True
        finally:
            self.client.close()  # ← Closes connection
```

**What happens**:
- Creates a `ZerobusIngestClient` from the config
- Calls `client.connect()` to establish connection
- Calls `client.ingest_batch()` to send data
- Calls `client.close()` to cleanup

---

### **Step 4: `ZerobusIngestClient` Talks to Databricks**

**File**: `silabs_mlops/data/ingest/zerobus_client.py`

```python
# Line 60-75 (Connect method)
def connect(self) -> None:
    """Initialize ZeroBus stream connection."""
    self._sdk = ZerobusSdk(self.server_endpoint, self.workspace_url)  # ← Real SDK!
    
    table_properties = TableProperties(self.table_name)
    options = StreamConfigurationOptions(record_type=RecordType.JSON)
    
    self._stream = self._sdk.create_stream(  # ← Create stream
        self.client_id,
        self.client_secret,
        table_properties,
        options,
    )

# Line 77-91 (Ingest record method)
def ingest_record(self, record: Dict[str, Any], wait_for_ack: bool = True) -> None:
    """Ingest a single JSON record into ZeroBus."""
    ack = self._stream.ingest_record(record)  # ← Send to Databricks!
    
    if wait_for_ack:
        ack.wait_for_ack()  # ← Wait for confirmation

# Line 93-100 (Ingest batch method)
def ingest_batch(self, records: List[Dict[str, Any]], ...) -> None:
    """Ingest multiple records sequentially."""
    for record in records:
        self.ingest_record(record, wait_for_ack=wait_for_ack)
```

**What happens**:
- Uses the official Databricks SDK: `ZerobusSdk` (from `databricks-zerobus-ingest-sdk`)
- Creates a stream to your Databricks table
- Sends each record via `self._stream.ingest_record(record)`
- Waits for acknowledgment from Databricks
- Data lands in your Databricks Delta Lake table!

---

## 📊 Visual Flow with File Locations

```
User Code
    ↓
┌─────────────────────────────────────────────────────────┐
│ silabs_mlops/data/__init__.py                          │
│                                                         │
│ data.config(...)                                        │
│   → creates IngestConfig (from ingest/config.py)      │
│   → stores in _config                                   │
│                                                         │
│ data.ingest(my_data)                                    │
│   → creates DataIngestor(_config)                      │
└─────────────────┬───────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────────────────────┐
│ silabs_mlops/data/ingest/ingestor.py                   │
│                                                         │
│ DataIngestor.__init__(config)                          │
│   → creates ZerobusIngestClient(config.*)              │
│                                                         │
│ DataIngestor.ingest(data)                              │
│   → calls client.connect()                             │
│   → calls client.ingest_batch(records)                 │
│   → calls client.close()                               │
└─────────────────┬───────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────────────────────┐
│ silabs_mlops/data/ingest/zerobus_client.py             │
│                                                         │
│ ZerobusIngestClient.connect()                          │
│   → ZerobusSdk(endpoint, workspace)  ← Real SDK!      │
│   → sdk.create_stream(...)                             │
│                                                         │
│ ZerobusIngestClient.ingest_batch(records)              │
│   → for each record:                                    │
│       stream.ingest_record(record)  ← Sends to DB!    │
│       ack.wait_for_ack()                                │
└─────────────────┬───────────────────────────────────────┘
                  ↓
         ┌────────────────────┐
         │ Databricks ZeroBus │
         │ (Official SDK)     │
         └────────┬───────────┘
                  ↓
         ┌────────────────────┐
         │ Databricks Delta   │
         │ Lake (Bronze)      │
         └────────────────────┘
```

---

## 🎯 Summary

| Step | File | What Happens |
|------|------|--------------|
| 1 | `data/__init__.py` | `data.config()` creates `IngestConfig`, stores in `_config` |
| 2 | `data/__init__.py` | `data.ingest()` creates `DataIngestor` with `_config` |
| 3 | `ingest/ingestor.py` | `DataIngestor` creates `ZerobusIngestClient` |
| 4 | `ingest/zerobus_client.py` | `ZerobusIngestClient.connect()` uses real SDK |
| 5 | `ingest/zerobus_client.py` | `ZerobusIngestClient.ingest_batch()` sends data |
| 6 | External | `databricks-zerobus-ingest-sdk` sends to Databricks |
| 7 | External | Data appears in Databricks Delta Lake table |

**Users only see steps 1 and 2. Everything else is hidden!** 🎉
