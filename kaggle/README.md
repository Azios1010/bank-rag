# Kaggle embedding job

This folder contains the offline embedding job for the experimental policy
index. It never calls the configured application LLM.

## Model contract

- Model: `Qwen/Qwen3-Embedding-0.6B`
- Dimension: `1024`
- Similarity: cosine
- Stored vectors: L2-normalized `float32`
- Kaggle-safe inference: FP16, sequence length `3072`, batch size `2`
- Document input: policy title, heading path and chunk content
- Query input: the fixed retrieval instruction in `embedding-job.json`

The notebook resolves `requested_revision` to an immutable Hugging Face commit
and records that commit in every output row and in the generated manifest.

## Kaggle setup

1. Create a new **Private Dataset** from
   `dist/bank-rag-kaggle-private-dataset.zip`.
2. Create a notebook and upload `bank-rag-qwen3-embedding.ipynb`.
3. Attach the private Dataset to the notebook.
4. Select a GPU accelerator and enable Internet so Hugging Face model weights
   can be downloaded.
5. Run all cells.
6. Download these files from `/kaggle/working`:
   - `embeddings.parquet`
   - `embedding-manifest.json`
   - `embedding-run-report.json`

The notebook finds `policy-chunks.jsonl` recursively under `/kaggle/input`. If
Kaggle keeps the upload as one ZIP file, the notebook reads and stages the
required files automatically. The Kaggle username and Dataset slug are
intentionally not hard-coded.

If a prior run ended with CUDA OOM, restart the Kaggle session before running
the updated notebook. Restarting releases allocations retained by the failed
kernel.

## Safety boundary

The packaged dataset contains public policy text only. It excludes `.env`,
credentials, raw case files, customer data, Git history, application source and
PDF originals.

The current source registry is `IN_REVIEW`, so the generated artifact is an
experimental index. Do not import it into a production knowledge base until
the relevant sources have been marked `REVIEWED` and the bundle is regenerated.
