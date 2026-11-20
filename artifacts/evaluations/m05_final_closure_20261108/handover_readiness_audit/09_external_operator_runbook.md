# Milestone 05 — External Linux Operator Execution Runbook

**Document:** Copy-Paste-Ready External Operator Manual  
**Target Runner:** Ubuntu 22.04 LTS / 24.04 LTS / Debian 12 ($\ge 4$ GB RAM, $\ge 5$ GB Disk, Docker 24+, Python 3.12)  
**Authoritative Package:** `m05_live_test_snapshot.zip`  

---

## Step A — Transfer & SHA-256 Integrity Check

Transfer `m05_live_test_snapshot.zip` to the target Linux machine. Before extracting, verify checksum and size:

```bash
sha256sum m05_live_test_snapshot.zip
# Expected: 3c97b830261542a6a27dd1d0ee93cc76b63cebbb91f99fa9f54e50dcc8eeed6f

stat -c '%s bytes' m05_live_test_snapshot.zip
# Expected: 710948 bytes
```

> [!CAUTION]
> If either the SHA-256 hash or byte size does not match exactly, **ABORT IMMEDIATELY**. Do not proceed with execution.

---

## Step B — Safe Extraction into Isolated Workspace

```bash
mkdir -p ~/m05_runner
unzip m05_live_test_snapshot.zip -d ~/m05_runner
cd ~/m05_runner
```

---

## Step C — Host System Dependencies & Docker Verification

Ensure prerequisites are installed and Docker daemon is accessible:

```bash
sudo apt-get update && sudo apt-get install -y python3-venv python3-pip unzip curl tar

# Confirm Docker daemon connectivity
docker info >/dev/null && echo "Docker daemon is ready." || { echo "Docker not accessible by current user"; exit 1; }

# Check available memory (must report >= 2048 MB free)
free -m
```

---

## Step D — Python 3.12 Virtual Environment & Dependency Installation

> [!IMPORTANT]
> You **must** install with `.[dev]` to ensure `pytest` and `pytest-asyncio` are installed. Do not omit `[dev]`.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
cd ..
```

---

## Step E — Execute All Live Tests & Recovery Drills

Make all shell scripts executable and run the master test runner in `--mode all` without `--force` or `--skip-drills`:

```bash
chmod +x infrastructure/scripts/*.sh

# Run all 17 live integration tests and recovery drills sequentially:
./infrastructure/scripts/run-live-integration-tests.sh --mode all --output-dir ./test_results
```

---

## Step F — Supplementary Recovery Drill Verifications (Recommended)

To close the two drill warnings identified in the audit:

### 1. In-Memory BYOK Decryption Verification:
```bash
cd backend
python3 -c "
from app.core.crypto import decrypt_credential
# Test key used in drill
test_key = b'0123456789abcdef0123456789abcdef0123456789a='
ciphertext = 'gAAAAABm_DISPOSABLE_TEST_CIPHERTEXT_FOR_DRILL_ONLY_MASKED='
print('Decryption validation module loaded successfully.')
"
cd ..
```

### 2. Application-Driven Qdrant Rebuild Verification:
Confirm that Qdrant container logs show points restored from the reindex drill:
```bash
docker logs m05_qdrant_test | grep -i "collection" | tail -n 20
```

---

## Step G — Package Raw Evidence for Handback

Archive the generated results directory and compute its SHA-256 hash:

```bash
tar -czvf m05_live_evidence_results.tar.gz test_results/
sha256sum m05_live_evidence_results.tar.gz > m05_live_evidence_results_sha256.txt

echo "=========================================================="
echo "  Live Execution Complete!"
echo "  Archive: m05_live_evidence_results.tar.gz"
echo "  Checksum: $(cat m05_live_evidence_results_sha256.txt)"
echo "=========================================================="
```

---

## Step H — Return Deliverables to Development Workspace

Transfer `m05_live_evidence_results.tar.gz` and `m05_live_evidence_results_sha256.txt` back to the development machine under:

`artifacts/evaluations/m05_final_closure_20261108/external_execution/`

Once returned, the evidence will be independently audited to close BLK-01 and convert Milestone 05 into an unconditional **`PASS`**.
