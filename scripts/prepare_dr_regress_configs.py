"""Generate dev-regression configs for the W4 vs direct-residual comparison.

Each output config derives from the frozen round-3 dev site config, stamps the
release fingerprint of the inference service that will serve the candidate, and
recomputes the freeze hash so ``evaluate_webarena_online.py`` validation accepts
it. These are development configs only; they are not eligible for final holdout
claims.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITES = ("gitlab", "reddit", "shopping")
FINGERPRINTS = {
    "w4": "5febb11f155cdbdd6ae60470b8756fa572a64ad207fb154711268300ce70e4f3",
    "dr": "5a23310a6ccb5fc9cfffb9759837a22165deee4cd173b942f64cf4e28dc42134",
}


def freeze_hash(payload: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def main() -> int:
    for site in SITES:
        source = ROOT / f"configs/webarena_p0_round3_dev_{site}.json"
        base = json.loads(source.read_text(encoding="utf-8"))
        for mode, fingerprint in FINGERPRINTS.items():
            cfg = dict(base)
            cfg["benchmark"] = (
                f"Round-3 dev {site} direct-residual online regression ({mode})"
            )
            cfg["release_fingerprint_sha256"] = fingerprint
            cfg.pop("freeze_sha256", None)
            cfg["freeze_sha256"] = freeze_hash(cfg)
            path = ROOT / f"configs/webarena_dr_regress_{site}_{mode}.json"
            path.write_text(
                json.dumps(cfg, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"wrote {path.relative_to(ROOT)} freeze={cfg['freeze_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
