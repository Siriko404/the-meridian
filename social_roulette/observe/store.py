"""Parquet store — chunked, zstd-compressed match records.

Records are written in batches (one Parquet file per N matches) so no single file
must be loaded whole. Single-match views read with a match_id filter (predicate
pushdown); aggregations stream row-group batches. Both are memory-safe.
"""
import os

import pyarrow as pa
import pyarrow.parquet as pq
import pyarrow.dataset as ds

from .match import run_match
from . import events as E

SCHEMA = pa.schema([
    ("match_id", pa.string()), ("seq", pa.int32()), ("turn", pa.int32()),
    ("actor", pa.int16()), ("type", pa.string()), ("target", pa.int16()),
    ("item", pa.string()), ("bullet", pa.string()), ("damage", pa.int16()),
    ("killed", pa.bool_()), ("extra", pa.string()),
])


def write_batch(rows, out_dir, batch_id, compression_level=19):
    os.makedirs(out_dir, exist_ok=True)
    table = pa.Table.from_pylist(rows, schema=SCHEMA)
    path = os.path.join(out_dir, f"matches_{batch_id:05d}.parquet")
    pq.write_table(table, path, compression="zstd", compression_level=compression_level)
    return path


def record_matches(out_dir, seeds, policies_fn=None, num_players=5, batch_size=1000):
    """Play `seeds` matches, flush to Parquet every `batch_size` matches. Returns file paths."""
    buf, paths, count, batch_id = [], [], 0, 0
    for seed in seeds:
        pols = policies_fn(seed) if policies_fn else {}
        res = run_match(seed, pols, num_players=num_players, match_id=seed, record=True)
        buf.extend(res["rows"])
        count += 1
        if count % batch_size == 0:
            paths.append(write_batch(buf, out_dir, batch_id))
            buf, batch_id = [], batch_id + 1
    if buf:
        paths.append(write_batch(buf, out_dir, batch_id))
    return paths


def read_match(out_dir, match_id):
    dset = ds.dataset(out_dir, format="parquet")
    rows = dset.to_table(filter=ds.field("match_id") == str(match_id)).to_pylist()
    rows.sort(key=lambda r: r["seq"])
    return rows


def iter_batches(out_dir, columns=None, batch_size=100_000):
    dset = ds.dataset(out_dir, format="parquet")
    yield from dset.to_batches(columns=columns, batch_size=batch_size)
