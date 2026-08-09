#!/usr/bin/env python3
"""
encryptor.py — Simulador NO DESTRUCTIVO del PFG.

Cifra ficheros solo dentro de rutas whitelisted. Cualquier intento fuera
aborta con error. Clave fija de laboratorio para poder descifrar como
red de seguridad si algo se cuelga.
"""

import argparse
import os
import sys
import json
import time
from pathlib import Path

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:
    print("ERROR: pip install cryptography", file=sys.stderr)
    sys.exit(2)

# WHITELIST estricta
WHITELIST = [
    "/opt/labprueba",
    "/home/lab/labprueba",
    "/tmp/labprueba",
]

# Clave fija del laboratorio (SOLO para PFG, nunca en producción)
LAB_KEY = bytes.fromhex("00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff")

LOG_PATH = "/var/log/lab_encryptor.log"

def log(event, **kwargs):
    rec = {"ts": time.time_ns(), "event": event, **kwargs}
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a") as f:
            f.write(json.dumps(rec) + "\n")
    except (PermissionError, OSError):
        pass
    print(json.dumps(rec), file=sys.stderr)

def whitelist_check(path):
    abs_path = os.path.realpath(path)
    for allowed in WHITELIST:
        if abs_path.startswith(os.path.realpath(allowed)):
            return True
    log("whitelist_violation", attempted=abs_path)
    sys.exit(f"FATAL: {abs_path} fuera de whitelist. Abortando.")

def encrypt_file(path):
    aesgcm = AESGCM(LAB_KEY)
    nonce = os.urandom(12)
    with open(path, "rb") as f:
        plaintext = f.read()
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    out_path = str(path) + ".encrypted"
    with open(out_path, "wb") as f:
        f.write(b"PFGLAB01")   # marker de laboratorio
        f.write(nonce)
        f.write(ciphertext)
    os.unlink(path)
    return out_path

def decrypt_file(path):
    aesgcm = AESGCM(LAB_KEY)
    with open(path, "rb") as f:
        marker = f.read(8)
        if marker != b"PFGLAB01":
            raise ValueError("no es fichero del laboratorio")
        nonce = f.read(12)
        ciphertext = f.read()
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    out_path = str(path).removesuffix(".encrypted")
    with open(out_path, "wb") as f:
        f.write(plaintext)
    os.unlink(path)
    return out_path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True)
    parser.add_argument("--action", required=True, choices=["encrypt", "decrypt"])
    args = parser.parse_args()

    whitelist_check(args.dir)
    log("start", action=args.action, dir=args.dir)

    target = Path(args.dir)
    if args.action == "encrypt":
        files = [f for f in target.iterdir()
                 if f.is_file() and not f.name.endswith(".encrypted")
                 and not f.name.startswith(".")]
    else:
        files = [f for f in target.iterdir()
                 if f.is_file() and f.name.endswith(".encrypted")]

    count = 0
    for f in files:
        whitelist_check(f)
        try:
            if args.action == "encrypt":
                encrypt_file(f)
            else:
                decrypt_file(f)
            count += 1
        except Exception as e:
            log("error", file=str(f), error=str(e))

    log("end", action=args.action, count=count)
    print(f"OK: {args.action} {count} ficheros")

if __name__ == "__main__":
    main()
