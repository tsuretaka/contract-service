#!/usr/bin/env python3
"""Idempotently migrate the legacy contract-service export into D1 and R2."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path


def sql(value):
    if value is None:
        return "NULL"
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return "'" + str(value).replace("'", "''") + "'"


def utc(value):
    if not value:
        return None
    text = str(value).replace(" ", "T")
    return text if text.endswith("Z") or "+" in text[10:] else text + "Z"


def storage_key(path):
    text = str(path)
    if text.startswith("supabase://contracts/"):
        text = text[len("supabase://contracts/"):]
    elif text.startswith("contracts/"):
        text = text[len("contracts/"):]
    return "legacy/contracts/" + text.lstrip("/")


def run(command, cwd):
    subprocess.run(command, cwd=cwd, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("export", type=Path)
    parser.add_argument("--apply", action="store_true", help="Upload objects and import rows. Default is validation only.")
    parser.add_argument("--database", default="contract-service-poc")
    parser.add_argument("--bucket", default="contract-service-poc")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    cloudflare_dir = Path(__file__).resolve().parents[1]
    bundle = json.loads(args.export.read_text(encoding="utf-8"))
    canonical = json.dumps(bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(canonical).hexdigest()
    source_project = bundle["source_project"]
    objects = {item["name"]: item for item in bundle["storage_objects"]}
    signed_names = set(objects)
    original_hashes = {c.get("pdf_sha256") for c in bundle["contracts"] if c.get("pdf_sha256")}
    failures = []

    with tempfile.TemporaryDirectory(prefix="contract-migration-") as temp_name:
        temp = Path(temp_name)
        downloaded = {}
        for index, item in enumerate(bundle["storage_objects"], 1):
            name = item["name"]
            target = temp / name
            target.parent.mkdir(parents=True, exist_ok=True)
            url = f"https://{source_project}.supabase.co/storage/v1/object/public/contracts/{urllib.parse.quote(name, safe='/')}"
            try:
                urllib.request.urlretrieve(url, target)
                size = target.stat().st_size
                if size != int(item["size"]):
                    raise ValueError(f"size mismatch: expected {item['size']}, got {size}")
                file_hash = hashlib.sha256(target.read_bytes()).hexdigest()
                if name.startswith("uploads/") and Path(name).stem in original_hashes and file_hash != Path(name).stem:
                    raise ValueError(f"SHA-256 mismatch: {file_hash}")
                downloaded[name] = {"path": target, "size": size, "sha256": file_hash}
            except Exception as exc:
                failures.append({"object": name, "error": str(exc)})
            print(f"validated {index}/{len(objects)}: {name}")

        if failures:
            raise SystemExit(json.dumps({"validation_failures": failures}, ensure_ascii=False, indent=2))

        imported_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        statements = ["PRAGMA foreign_keys = ON;"]
        for contract in bundle["contracts"]:
            contract_id = contract["id"]
            signed_name = f"signed/{contract_id}_signed.pdf"
            certificate_name = f"signed/{contract_id}_cert.pdf"
            values = [
                contract_id, contract["title"], contract["status"], storage_key(contract["pdf_path"]),
                contract.get("pdf_sha256"), storage_key(signed_name) if signed_name in signed_names else None,
                storage_key(certificate_name) if certificate_name in signed_names else None,
                utc(contract["created_at"]), utc(contract.get("sent_at")), utc(contract.get("signed_at")),
                utc(contract.get("voided_at")), "legacy_supabase",
            ]
            statements.append(
                "INSERT INTO cs_contracts (id,title,status,pdf_path,pdf_sha256,signed_pdf_path,certificate_path,created_at,sent_at,signed_at,voided_at,source_system) VALUES ("
                + ",".join(map(sql, values))
                + ") ON CONFLICT(id) DO UPDATE SET title=excluded.title,status=excluded.status,pdf_path=excluded.pdf_path,pdf_sha256=excluded.pdf_sha256,signed_pdf_path=excluded.signed_pdf_path,certificate_path=excluded.certificate_path,created_at=excluded.created_at,sent_at=excluded.sent_at,signed_at=excluded.signed_at,voided_at=excluded.voided_at WHERE cs_contracts.source_system='legacy_supabase';"
            )
        for party in bundle["parties"]:
            values = [party["id"], party["contract_id"], party["role"], party["name"], party.get("email"), utc(party["created_at"])]
            statements.append("INSERT INTO cs_parties (id,contract_id,role,name,email,created_at) VALUES (" + ",".join(map(sql, values)) + ") ON CONFLICT(id) DO UPDATE SET name=excluded.name,email=excluded.email;")
        for session in bundle["signing_sessions"]:
            revoked_at = None if session.get("used_at") else imported_at
            values = [session["id"], session["contract_id"], session["signer_party_id"], session["token_hash"], utc(session["expires_at"]), None, utc(session.get("used_at")), revoked_at, utc(session["created_at"])]
            statements.append("INSERT INTO cs_signing_sessions (id,contract_id,signer_party_id,token_hash,expires_at,processing_at,used_at,revoked_at,created_at) VALUES (" + ",".join(map(sql, values)) + ") ON CONFLICT(id) DO UPDATE SET expires_at=excluded.expires_at,used_at=excluded.used_at,revoked_at=excluded.revoked_at;")
        for event in bundle["audit_events"]:
            values = [event["id"], event.get("contract_id"), event["actor_type"], event.get("actor_reference"), event["event_type"], utc(event["occurred_at"]), event.get("ip_address"), event.get("user_agent"), event.get("metadata_json"), event["previous_hash"], event["record_hash"], "legacy_supabase"]
            statements.append("INSERT INTO cs_legacy_audit_events (id,contract_id,actor_type,actor_reference,event_type,occurred_at,ip_address,user_agent,metadata_json,previous_hash,record_hash,source_system) VALUES (" + ",".join(map(sql, values)) + ") ON CONFLICT(id) DO UPDATE SET metadata_json=excluded.metadata_json;")
        run_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"legacy-contract-export:{digest}"))
        counts = [len(bundle[k]) for k in ("contracts", "parties", "signing_sessions", "audit_events", "storage_objects")]
        migration_values = [run_id, "legacy_supabase", digest, utc(bundle["exported_at"]), imported_at, *counts]
        statements.append("INSERT OR IGNORE INTO cs_migration_runs (id,source_system,source_digest,exported_at,imported_at,contract_count,party_count,session_count,audit_count,object_count) VALUES (" + ",".join(map(sql, migration_values)) + ");")
        sql_file = temp / "legacy-import.sql"
        sql_file.write_text("\n".join(statements) + "\n", encoding="utf-8")

        report = {
            "source_project": source_project,
            "source_digest": digest,
            "counts": dict(zip(("contracts", "parties", "signing_sessions", "audit_events", "storage_objects"), counts)),
            "downloaded_bytes": sum(x["size"] for x in downloaded.values()),
            "validation_failures": failures,
            "apply_requested": args.apply,
        }
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        if not args.apply:
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return

        for index, (name, item) in enumerate(downloaded.items(), 1):
            run(["npx", "wrangler", "r2", "object", "put", f"{args.bucket}/{storage_key(name)}", f"--file={item['path']}", "--content-type=application/pdf", "--remote"], cloudflare_dir)
            print(f"uploaded {index}/{len(downloaded)}: {name}")
        run(["npx", "wrangler", "d1", "execute", args.database, "--remote", f"--file={sql_file}"], cloudflare_dir)
        print(json.dumps({**report, "applied": True}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
